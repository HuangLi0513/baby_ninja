# -*- coding: utf-8 -*-

evented = False
multi_process = False

import os
os.environ['TZ'] = 'UTC' # Set the timezone...
import time              # ... *then* import time.
del os
del time

SUPERUSER_ID = 1

#----------------------------------------------------------
# Imports
#----------------------------------------------------------
import conf
import tools
import release
import netsvc
import service

#----------------------------------------------------------
# Model classes, fields, api decorators, and translations
#----------------------------------------------------------


#----------------------------------------------------------
# Other imports, which may require stuff from above
#----------------------------------------------------------
import cli