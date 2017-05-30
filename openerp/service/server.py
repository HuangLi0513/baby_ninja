# -*- coding: utf-8 -*-
import os
import sys
import socket
import errno
import platform
import threading
import signal
import time
import logging
import werkzeug.serving
import datetime

_logger = logging.getLogger(__name__)

import openerp
from openerp.tools import config

SLEEP_INTERVAL = 60     # 1 min


#----------------------------------------------------------
# Werkzeug WSGI servers patched
#----------------------------------------------------------
class LoggingBaseWSGIServerMixIn(object):
    def handle_error(self, request, client_address):
        t, e, _ = sys.exc_info()
        if t == socket.error and e.errno == errno.EPIPE:
            # broken pipe, ignore error
            return
        _logger.exception('Exception happened during processing of request from %s', client_address)

class RequestHandler(werkzeug.serving.WSGIRequestHandler):
    def setup(self):
        # flag the current thread as handling a http request
        super(RequestHandler, self).setup()
        me = threading.currentThread()
        me.name = 'openerp.service.http.request.%s' % (me.ident,)

class ThreadedWSGIServerReloadable(LoggingBaseWSGIServerMixIn, werkzeug.serving.ThreadedWSGIServer):
    """ werkzeug Threaded WSGI Server patched to allow reusing a listen socket
    given by the environement, this is used by autoreload to keep the listen
    socket open when a reload happens.
    """
    def __init__(self, host, port, app):
        super(ThreadedWSGIServerReloadable, self).__init__(host, port, app,
                                                           handler=RequestHandler)

    def server_bind(self):
        envfd = os.environ.get('LISTEN_FDS')
        print 'envfd: %s' %envfd
        if envfd and os.environ.get('LISTEN_PID') == str(os.getpid()):
            print os.environ.get('LISTEN_PID')
            print os.getpid()
            self.reload_socket = True
            self.socket = socket.fromfd(int(envfd), socket.AF_INET, socket.SOCK_STREAM)
            # should we os.close(int(envfd)) ? it seem python duplicate the fd.
        else:
            self.reload_socket = False
            super(ThreadedWSGIServerReloadable, self).server_bind()

    def server_activate(self):
        if not self.reload_socket:
            super(ThreadedWSGIServerReloadable, self).server_activate()

#----------------------------------------------------------
# Servers: Threaded, Gevented and Prefork
#----------------------------------------------------------

class CommonServer(object):
    def __init__(self, app):
        # TODO Change the xmlrpc_* options to http_*
        self.app = app
        # config
        self.interface = config['xmlrpc_interface'] or '0.0.0.0'
        self.port = config['xmlrpc_port']
        # runtime
        self.pid = os.getpid()

    def close_socket(self, sock):
        """ Closes a socket instance cleanly
        :param sock: the network socket to close
        :type sock: socket.socket
        """
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except socket.error, e:
            # On OSX, socket shutdowns both sides if any side closes it
            # causing an error 57 'Socket is not connected' on shutdown
            # of the other side (or something), see
            # http://bugs.python.org/issue4397
            # note: stdlib fixed test, not behavior
            if e.errno != errno.ENOTCONN or platform.system() not in ['Darwin', 'Windows']:
                raise
        sock.close()

class ThreadedServer(CommonServer):
    def __init__(self, app):
        super(ThreadedServer, self).__init__(app)
        self.main_thread_id = threading.currentThread().ident
        print 'main_thread_id: %s' %self.main_thread_id
        # Variable keeping track of the number of calls to the signal handler defined
        # below. This variable is monitored by ``quit_on_signals()``.
        self.quit_signals_received = 0

        #self.socket = None
        self.httpd = None

    def signal_handler(self, sig, frame):
        if sig in [signal.SIGINT, signal.SIGTERM]:
            # shutdown on kill -INT or -TERM
            self.quit_signals_received += 1
            if self.quit_signals_received > 1:
                # logging.shutdown was already called at this point.
                sys.stderr.write("Forced shutdown.\n")
                os._exit(0)
        elif sig == signal.SIGHUP:
            # restart on kill -HUP
            self.quit_signals_received += 1

    def cron_thread(self, number):
        while True:
            time.sleep(SLEEP_INTERVAL + number)     # Steve Reich timing style
            registries = openerp.modules.registry.RegistryManager.registries
            print registries
            _logger.info('cron%d polling for jobs', number)
            for db_name, registry in registries.iteritems():
                print db_name, registry
                while registry.ready:
                    acquired = openerp.addons.base.ir.ir_cron.ir_cron._acquire_job(db_name)
                    if not acquired:
                        break

    def cron_spawn(self):
        """ Start the above runner function in a daemon thread.

        The thread is a typical daemon thread: it will never quit and must be
        terminated when the main process exits - with no consequence (the processing
        threads it spawns are not marked daemon).

        """
        # Force call to strptime just before starting the cron thread
        # to prevent time.strptime AttributeError within the thread.
        # See: http://bugs.python.org/issue7980
        datetime.datetime.strptime('2012-01-01', '%Y-%m-%d')
        for i in range(openerp.tools.config['max_cron_threads']):
            print 'threads: %s' %i
            def target():
                self.cron_thread(i)
            t = threading.Thread(target=target, name="openerp.service.cron.cron%d" % i)
            t.setDaemon(True)
            t.start()
            _logger.info("cron%d started!" % i)

    def http_thread(self):
        def app(e, s):
            return self.app(e, s)
        self.httpd = ThreadedWSGIServerReloadable(self.interface, self.port, app)
        self.httpd.serve_forever()

    def http_spawn(self):
        t = threading.Thread(target=self.http_thread, name="openerp.service.httpd")
        t.setDaemon(True)
        t.start()
        print 'http thread: %s' %t.ident
        _logger.info('HTTP service (werkzeug) running on %s:%s', self.interface, self.port)

    def start(self, stop=False):
        _logger.info("Setting signal handlers")
        if os.name == 'nt':
            import win32api
            win32api.SetConsoleCtrlHandler(lambda sig: self.signal_handler(sig, None), 1)

        test_mode = config['test_enable'] or config['test_file']
        if test_mode or (config['xmlrpc'] and not stop):
            # some tests need the http deamon to be available...
            print 'http_spawn begin'
            self.http_spawn()
            print 'http_spawn end'

        if not stop:
            # only relevant if we are not in "--stop-after-init" mode
            print 'cron_spawn begin'
            self.cron_spawn()
            print 'cron_spawn end'

    def stop(self):
        """ Shutdown the WSGI server. Wait for non deamon threads.
        """
        _logger.info("Initiating shutdown")
        _logger.info("Hit CTRL-C again or send a second signal to force the shutdown.")

        if self.httpd:
            self.httpd.shutdown()
            self.close_socket(self.httpd.socket)

        # Manually join() all threads before calling sys.exit() to allow a second signal
        # to trigger _force_quit() in case some non-daemon threads won't exit cleanly.
        # threading.Thread.join() should not mask signals (at least in python 2.5).
        me = threading.currentThread()
        _logger.info('current thread: %r', me)
        for thread in threading.enumerate():
            _logger.info('process %r (%r)', thread, thread.isDaemon())
            if thread != me and not thread.isDaemon() and thread.ident != self.main_thread_id:
                while thread.isAlive():
                    _logger.info('join and sleep')
                    # Need a busyloop here as thread.join() masks signals
                    # and would prevent the forced shutdown.
                    thread.join(0.05)
                    time.sleep(0.05)

        _logger.info('--')
        openerp.modules.registry.RegistryManager.delete_all()
        logging.shutdown()

    def run(self, preload=None, stop=False):
        """ Start the http server and the cron thread then wait for a signal.

        The first SIGINT or SIGTERM signal will initiate a graceful shutdown while
        a second one if any will force an immediate exit.
        """
        self.start(stop=stop)
        print 'start out'

        rc = preload_registries(preload)
        print 'rc: %s' %rc

        if stop:
            self.stop()
            return rc

        # Wait for a first signal to be handled. (time.sleep will be interrupted
        # by the signal handler.) The try/except is for the win32 case.
        try:
            while self.quit_signals_received == 0:
                time.sleep(60)
        except KeyboardInterrupt:
            pass

        print 'run end'
        self.stop()

    def reload(self):
        os.kill(self.pid, signal.SIGHUP)

server = None

def start(preload=None, stop=False):
    """ Start the openerp http server and cron processor.
    """
    global server
    # if openerp.evented:
    #     print 'GeventServer'
    #     server = GeventServer(openerp.service.wsgi_server.application)
    # elif config['workers']:
    #     print 'PreforkServer'
    #     server = PreforkServer(openerp.service.wsgi_server.application)
    # else:
    #     print 'ThreadServer'
    #     server = ThreadedServer(openerp.service.wsgi_server.application)
    server = ThreadedServer(openerp.service.wsgi_server.application)

    print 'pid: %s' %os.getpid()

    print 'run begin'
    rc = server.run(preload, stop)
    print 'run end'

    print 'rc: %s' %rc
    return rc if rc else 0