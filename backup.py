#!/usr/local/bin/python
#===============================================================================
# backup.py: uses .htpasswd bypass via SAML to download each user's cal over http
# each user done individually (a) to get user-created cals, (b) to reduce risk
#    - creates dir for today
#    - downloads csv of global contact list
#    - subscribes _backup user to all resources (to ensure that rooms, etc get backed up)
#    - sets random identical .htpasswd password for all current users (minus skipNames)
#    - logs in via SAML to each user's account and downloads the exportical.zip file
#===============================================================================

# base python
import time
from datetime import datetime, timedelta
import string
import random
import subprocess
import sys
import os

# you may need to install these
from ConfigParser import SafeConfigParser
import mechanize
from pyparsing import makeHTMLTags,SkipTo

import gdata.apps.service
import gdata.contacts.service
import gdata.calendar.service
import gdata.calendar.client

##############################################
## Google Apps Clients/Services Connections ##
##############################################

def openGoogleCalendarService(loginEmail, loginPass, googleSource):
    # open Calendar Service connection
    calendar_service = gdata.calendar.service.CalendarService()
    calendar_service.email = loginEmail
    calendar_service.password = loginPass
    calendar_service.source = googleSource
    calendar_service.ProgrammaticLogin()
    return calendar_service
# end def OpenGoogleCalendarService()

def openGoogleContactsService(loginEmail, loginPass, googleSource):
    # open Contacts Service connection
    contacts_service = gdata.contacts.service.ContactsService()
    contacts_service.email = loginEmail
    contacts_service.password = loginPass
    contacts_service.source = googleSource
    contacts_service.ProgrammaticLogin()
    return contacts_service
# end def OpenGoogleContactsService()

## end Google Apps Clients/Services Connections ##


########################
## Contacts Functions ##
########################

# formats Google's contact output, includes all email addresses
def writeOutContacts(contactsFeed, contactsOut):
    for entry in contactsFeed.entry:
        if entry.title.text:
            contactsOut.write(entry.title.text)
            contactsOut.write(',')
            for email in entry.email:
                contactsOut.write(email.address + '\n')
# end def writeOutContacts

# connects to client and writes to saved file
# super helpful: http://code.google.com/googleapps/domain/shared_contacts/gdata_shared_contacts_api_reference.html
def backUpContacts(loginEmail, loginPass, loginDomain, contactsSaveFile, googleSource):
    gd_client = openGoogleContactsService(loginEmail, loginPass, googleSource)
    
    contactsOut = open(contactsSaveFile, 'w')
    # need to use a query rather than a straight feed to get around return limits
    contactsFeed = 'http://www.google.com/m8/feeds/contacts/' + loginDomain + '/full'
    contactsQuery = gdata.contacts.service.ContactsQuery(feed=contactsFeed)
    contactsQuery.max_results = 1000
                    
    try:
        contactsFeed = gd_client.GetContactsFeed(contactsQuery.ToUri())
    except gdata.service.RequestError:
        try: 
            print "WARN: contact download failed once: " +  " at " + time.strftime('%H:%M') + ".\n"
            contactsFeed = gd_client.GetContactsFeed(contactsQuery.ToUri())
        except gdata.service.RequestError:
            print "FAIL: contact download failed twice: " +  " at " + time.strftime('%H:%M') + ".\n"
        else: 
            print "OKAY: Got contact list on second try at " + time.strftime('%H:%M') + ".\n"
            writeOutContacts(contactsFeed)
    else:
        print "Downloaded contact list at " + time.strftime('%H:%M') + ".\n"
        writeOutContacts(contactsFeed, contactsOut)
    
    contactsOut.close()
# end def backUpContacts

## end Contacts Functions ##


#########################
## Resources Functions ##
#########################

    # Resources currently on ice
    # http://code.google.com/googleapps/domain/calendar_resource/docs/1.0/calendar_resource_developers_guide_protocol.html#retrieving_all_calendars
    # http://code.google.com/apis/calendar/data/2.0/reference.html#Calendar_feeds
    #===============================================================================
    
    ### Part One - list resources
    ## establish authentication
    #gapps_service = gdata.apps.service.AppsService()
    #gapps_service.email = loginEmail
    #gapps_service.password = loginPass
    #gapps_service.domain = loginDomain
    #gapps_service.ProgrammaticLogin()
    #
    ## get list of all resources into gresFeed
    #gres_client = gdata.calendar_resource.client.CalendarResourceClient(loginDomain)
    #gres_client.client_login(loginEmail, loginPass, loginDomain, 'apps', 'HOSTED')
    #gresFeedURI = gres_client.MakeResourceFeedUri()
    #gresFeed = gres_client.GetResourceFeed(gresFeedURI)
    #
    ### Part Two - Subscribe _backup to resource calendars
    ## ok, now we must subscribe _backup!
    #calendar_service = gdata.calendar.service.CalendarService()
    #calendar_service.email = loginEmail
    #calendar_service.password = loginPass
    #calendar_service.source = loginDomain
    #calendar_service.ProgrammaticLogin()
    #
    ## PROBLEM: InsertCalendarSubscription seems to add the _backup user to the owner list but NOT subscribe _backup
    ## so, checking with second stanza
    ## is there a delay between API reality and download reality?
    #for a_resource in gresFeed.entry:
    #    a_calendar = gdata.calendar.CalendarListEntry()
    #    a_calendar.id = atom.Id(text=a_resource.GetResourceEmail())
    #    # note: should the id be something liek http://www.google.com/calendar/feeds/default/allcalendars/full/apps.cul.columbia.edu_1i9d76i1ah8sk2ju23haqvvitk%40group.calendar.google.com ???
    #    returned_calendar = calendar_service.InsertCalendarSubscription(calendar=a_calendar)
    #    
    #    #print returned_calendar
    #    returned_calendar.hidden = gdata.calendar.Hidden(value='false')
    #    returned_calendar.selected = gdata.calendar.Selected(value='true')
    #    updated_calendar = calendar_service.UpdateCalendar(calendar=returned_calendar)

## end Resources Functions ##


################################
## Users / Accounts functions ##
################################

# returns list of active users, minus those in skipNames
def returnUsersList(loginEmail, loginPass, loginDomain, skipNames):
    # login info
    gapps_service = gdata.apps.service.AppsService()
    gapps_service.email = loginEmail
    gapps_service.password = loginPass
    gapps_service.domain = loginDomain
    gapps_service.ProgrammaticLogin()
    
    # retrieve a list of all users
    userFeed = gapps_service.RetrieveAllUsers()
    
    # filter out suspended users and the skipNames
    def filterUsers(googleFeedEntry):
        if googleFeedEntry.login.suspended == "false" : 
            if googleFeedEntry.title.text not in skipNames:
                return True
            else: 
                return False
        else:
            return False
    
    usersList = filter(filterUsers,userFeed.entry)
    return usersList
# end def returnUsersList

# sets all users to tonight's random bypass password
# this is possible because we're using a SAML authenticator that allows .htpasswd bypass
# it would be better to use oauth
def setRandomPassword(scpHtpasswdTo, usersList, loginUser, loginPass, logOut):
    # get current .htpasswd file from server
    subprocess.call(['scp', scpHtpasswdTo, '.htpasswd'], stderr=logOut)
    
    # make a random password between 12 and 16 chars
    randMin = 12
    randMax = 16
    # note: issue: using random.sample means every character in the password is unique
    randomPassword = "".join(random.sample(string.letters+string.digits,random.randint(randMin,randMax)))
    
    # set new password for each user
    for a_user in usersList:
        subprocess.call(["htpasswd", "-b", ".htpasswd", a_user.title.text, randomPassword], stderr=logOut)
    
    # also set the backup user's pass to the correct thing
    subprocess.call(["htpasswd", "-b", ".htpasswd", loginUser, loginPass], stderr=logOut)
        
    # upload back to server    
    subprocess.call(['scp', '.htpasswd', scpHtpasswdTo], stderr=logOut)
    
    return randomPassword

## end Users / Accounts functions ##


########################
## Calendar Functions ##
########################

# post-login, gets the iCal zip file for specific user
def getUseriCalZip(todaysDate, userName, samlResponse, br, logOut):
    samlResponseText = samlResponse.read()
    theStart,theEnd = makeHTMLTags("textarea")
    search = theStart + SkipTo(theEnd)("body")+ theEnd
            
    saml_resp_str = search.searchString(samlResponseText)[0].body
    relay_state_str = search.searchString(samlResponseText)[1].body
    
    fileNametoSave = todaysDate + "/" + userName + ".zip"
    
    br.select_form(name="acsForm")
    br["SAMLResponse"] = saml_resp_str
    br["RelayState"] = relay_state_str
    try: 
        br.submit()
    except:
        print "WARN: trouble downloading cal data for " + userName + ": " +  " at " + time.strftime('%H:%M') + ".\n"
        logOut.flush()
        time.sleep(60)
        try:
            br.submit()
        except:
            print "FAIL: can't open cal session for " + userName + ": " +  " at " + time.strftime('%H:%M') + ".\n"
            logOut.flush()
        else:
            print "OKAY - second try - retrieving cal data for user " + userName + " at " + time.strftime('%H:%M') + ".\n"
            logOut.flush()
            try: 
                br.retrieve('https://www.google.com/calendar/exporticalzip',fileNametoSave) 
            except:
                print "FAIL: can't open cal session for " + userName + ": " +  " at " + time.strftime('%H:%M') + ".\n"
                logOut.flush()
    else:
        print "Retrieving cal data for user " + userName + " at " + time.strftime('%H:%M') + ".\n"
        logOut.flush()
        try:
            br.retrieve('https://www.google.com/calendar/exporticalzip',fileNametoSave)
        except:
            print "FAIL: can't download cal data for " + userName + ": " +  " at " + time.strftime('%H:%M') + ".\n"
            logOut.flush()  
###### end def getUseriCalZip

# handles initial login to backup user calendar; calls getUseriCalZip for the rest
def backupUserCal(userName, loginURL, randomPassword, todaysDate, logOut):
        br=mechanize.Browser()
        try:
            br.open(loginURL)
        except:
            print "WARN: Trouble with initial connect for " + userName + ": " +  " at " + time.strftime('%H:%M') + ".\n"
            logOut.flush()
            time.sleep(60)
            try:
                br.open(loginURL)
            except:
                print "FAIL: gave up on initial connect for " + userName + ": " +  " at " + time.strftime('%H:%M') + ".\n"
                logOut.flush()
                return
            
        br.select_form(name="theform")
        br['username']=userName
        br['password']=randomPassword
        
        # get SAML login response
        try:
            samlResponse = br.submit()
        except:
            print "WARN: can't get past SAML for " + userName + ": " +  " at " + time.strftime('%H:%M') + ".\n"
            logOut.flush()
            time.sleep(60)
            try:
                samlResponse = br.submit()
            except:
                print "FAIL: can't get past SAML for " + userName + ": " +  " at " + time.strftime('%H:%M') + ".\n"
                logOut.flush()
            else:
                print "OKAY: Login succeeded (second time) for " + userName + " at " + time.strftime('%H:%M') + ".\n"
                getUseriCalZip(todaysDate, userName, samlResponse, br, logOut) 
        else:
            print "Login succeeded for " + userName + " at " + time.strftime('%H:%M') + ".\n"
            getUseriCalZip(todaysDate, userName, samlResponse, br, logOut)
###### end def backupUserCal

## end Calendar Functions ##


                                            #############################
                                            ##   ~~     main!    ~~    ##
                                            #############################

def main():
    #===============================================================================
    # Settings....
    #===============================================================================
    
    # skipNames: these names should not be backed up, and their passwords should not be touched
    skipNames = frozenset(['_sc_api', '_sc_api2', 'presentation_cul_user', 'cul', 'cornell', '_backup'])
    
    # get settings from external file
    config_file = '/opt/pytest/settings.ini'
    parser = SafeConfigParser()
    parser.read(config_file)

    # set working directory
    os.chdir("/opt/cal-backup")

    # login info for non-oauth apis like provisioning...
    loginUser = parser.get('settings', 'loginUser')
    loginPass = parser.get('settings', 'loginPass')
    loginDomain = parser.get('settings', 'loginDomain')
    loginEmail = loginUser + '@' + loginDomain
    loginURL = 'http://' + loginDomain
    
    # for resetting users' SAML passwords
    scpHtpasswdTo = parser.get('settings', 'scpHtpasswdTo')
    
    # oath stuff (not in use at the moment)
    consumerKey = loginDomain
    consumerSecret = parser.get('settings', 'oauth_secret')

    # add googleSource
    googleSource = loginDomain + ".backup.script"
    
    # where to save files
    todaysDate = time.strftime('%Y-%m-%d')
    contactsSaveFile = todaysDate + "/00-contacts.csv"
    logSaveFile = todaysDate + "/00-log.txt"
        
    #===============================================================================
    # Logging / Time... 
    #===============================================================================

    # if debug is true, errors go to the screen; there may be additional errors, too
    # if debug is false, everything is shunted to the log file 
    debug = False
    
    subprocess.call(['mkdir', todaysDate], stderr=subprocess.STDOUT)
    subprocess.call(['touch', logSaveFile], stderr=subprocess.STDOUT)
    logOut = open(logSaveFile, 'a')
    
    if not debug: 
        sys.stdout = logOut
        sys.stderr = logOut
        subprocess.STDOUT = logOut
    
    # start timer
    timeStart = datetime.now()
    print "Started at " + timeStart.strftime("%Y-%m-%d %H:%M:%S") + "\n"
    
    #===============================================================================
    # Back it all up...
    #===============================================================================
    
    # Back up current list of shared global contacts
    backUpContacts(loginEmail, loginPass, loginDomain, contactsSaveFile, googleSource)
    
    # Get full list of resources and subscribe _backup to all resources
    # subscribeResources()

    # Get current list of users from Google  
    usersList = returnUsersList(loginEmail, loginPass, loginDomain, skipNames)

    # For each user, set htpasswd to tonight's random password
    # it would be better to use oauth
    randomPassword = setRandomPassword(scpHtpasswdTo, usersList, loginUser, loginPass, logOut)

    # Back up the backup user's calendar...
    backupUserCal(loginUser, loginURL, loginPass, todaysDate, logOut)
    
    #  now download a backup copy of the calendars for each user
    for a_user in (usersList):
        backupUserCal(a_user.title.text, loginURL, randomPassword, todaysDate, logOut)
        
    #===============================================================================
    #  clean up....
    #===============================================================================
    timeEnd = datetime.now()
    timeElapsed = timeEnd - timeStart
    hoursElapsed = int(timeElapsed.seconds / 3600)
    minutesElapsed = int((timeElapsed.seconds - hoursElapsed*3600) / 60)
    print "Ended at " + timeEnd.strftime("%Y-%m-%d %H:%M:%S") + "\n"
    print 'Total time: %s hours, %s minutes (%s total seconds)' % (hoursElapsed, minutesElapsed, timeElapsed.seconds)
    
    logOut.close()
# end def of main()

if __name__ == '__main__':
    main()