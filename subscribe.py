#!/usr/local/bin/python
#===============================================================================
# subscribe.py: subscribes users to specified calendar
# looks for settings.ini for settings
#===============================================================================

# base python
import os
import sys
import subprocess
import time

# you may need to install these
from ConfigParser import SafeConfigParser
import atom

# tested against gdata-2.0.14
# http://code.google.com/p/gdata-python-client/
# http://code.google.com/p/gdata-python-client/source/browse/samples/oauth/TwoLeggedOAuthExample.py
import gdata.apps.service
import gdata.calendar.client
import gdata.gauth

########################
## Calendar Functions ##
########################

def returnUsersList(loginEmail, loginPass, loginDomain,skipNames):
    gapps_service = gdata.apps.service.AppsService()
    gapps_service.email = loginEmail
    gapps_service.password = loginPass
    gapps_service.domain = loginDomain
    gapps_service.ProgrammaticLogin()
    
    # retrieve a list of all users
    userFeed = gapps_service.RetrieveAllUsers()
    
    # filter out suspended users and the skipNames
    def filterUsers(googleFeedEntry):
        if googleFeedEntry.login.suspended == "true" or googleFeedEntry.title.text in skipNames:
            return False
        else: 
            return True
    
    usersList = filter(filterUsers,userFeed.entry)
    return usersList

def addSubscription(requestorId, consumerKey, consumerSecret, googleSource,calendarID):
    client = gdata.calendar.client.CalendarClient(googleSource)
    client.auth_token = gdata.gauth.TwoLeggedOAuthHmacToken(consumerKey, consumerSecret, requestorId)
    
    calendar = gdata.calendar.data.CalendarEntry()
    calendar.id = atom.data.Id(text=calendarID)
    calendar.hidden = gdata.calendar.data.HiddenProperty(value='false')
    calendar.selected = gdata.calendar.data.SelectedProperty(value='true')
    try:
        returned_calendar = client.InsertCalendarSubscription(calendar)
    except:
        print "Skipping " + requestorId

## end Calendar Functions ##

                                            #############################
                                            ##   ~~     main!    ~~    ##
                                            #############################

def main():
    # get settings from external file
    config_file = 'settings.ini'
    parser = SafeConfigParser()
    parser.read(config_file)

    # set working directory
    # take default from settings or set something here
    #baseDir = parser.get('settings', 'baseDir')
    baseDir = "/opt/provisioning"
    os.chdir(baseDir)
    
    # login info for non-oauth apis like provisioning...
    loginUser = parser.get('settings', 'loginUser')
    loginPass = parser.get('settings', 'loginPass')
    loginDomain = parser.get('settings', 'loginDomain')
    loginEmail = loginUser + '@' + loginDomain
    loginURL = 'http://' + loginDomain
    
    # oath stuff
    consumerKey = loginDomain
    consumerSecret = parser.get('settings', 'oauth_secret')
    
    # logging info
    todaysDate = time.strftime('%Y-%m-%d')
    contactsSaveFile = todaysDate + "/00-contacts.csv"
    logSaveFile = todaysDate + "/00-log.txt"
    scpHtpasswdTo = parser.get('settings', 'scpHtpasswdTo') 
    
    # add googleSource
    googleSource = loginDomain + ".subscribe.script"
    
    # don't subscribe these accounts to the calendar
    skipNames = frozenset(['_sc_api', '_sc_api2', 'presentation_cul_user', 'cul', 'cornell', '_backup'])
    
    # calendar ID we're subscribing to
    calendarID = 'apps.cul.columbia.edu_c74fh1l1um0bia8hedavtiogc8@group.calendar.google.com'
    
    #===============================================================================
    # Logging / Time... 
    #===============================================================================

    # if debug is true, errors go to the screen; there may be additional errors, too
    # if debug is false, everything is shunted to the log file 
    debug = True
    
    subprocess.call(['mkdir', todaysDate], stderr=subprocess.STDOUT)
    subprocess.call(['touch', logSaveFile], stderr=subprocess.STDOUT)
    logOut = open(logSaveFile, 'a')
    
    if not debug: 
        sys.stdout = logOut
        sys.stderr = logOut
        subprocess.STDOUT = logOut
    
    # start timer
    timeStart = time.time()
    print "Started at " + time.strftime('%Y-%m-%d %H:%M') + "\n"
    
    #===============================================================================
    # Subscribe all users in the domain....
    #===============================================================================
    
    usersList = returnUsersList(loginEmail, loginPass, loginDomain, skipNames)

    for a_user in (usersList):
        requestorId = a_user.title.text + "@" + loginDomain
        print "adding subscription for " + requestorId
        addSubscription(requestorId, consumerKey, consumerSecret, googleSource, calendarID)
        
    #===============================================================================
    #  clean up....
    #===============================================================================
    totalSecondsElapsed = time.time() - timeStart
    hoursElapsed = int(totalSecondsElapsed / 3600)
    minutesElapsed = int((totalSecondsElapsed - hoursElapsed*3600) / 60)
    print 'Total time: %s hours, %s minutes (%s total seconds)' % (hoursElapsed, minutesElapsed, totalSecondsElapsed)
    
    logOut.close()
# end def of main()

if __name__ == '__main__':
    main()    