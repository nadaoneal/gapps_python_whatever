#!/usr/local/bin/python
#===============================================================================
# backup.py: uses .htpasswd bypass via SAML to download each user's cal over http
# each user done individually (a) to get user-created cals, (b) to reduce risk
#    - creates dir for today
#    - downloads csv of global contact list
#    - subscribes _backup user to all resources (to ensure that rooms, etc get backed up)
#    - sets random identical .htpasswd password for all current users (minus skipNames)
#    - logs in via SAML to each user's account and downloads the exportical.zip file
# Warning: the login url is hardcoded in the middle of the script - "THIS IS THE URL TO YOUR LOGIN PAGE".
# Also search for "YOUR DOMAIN". Really terrible, I apologize. 
#===============================================================================

import time
import string
import random
import subprocess
import sys

import mechanize
from pyparsing import makeHTMLTags,SkipTo

import gdata.apps.service
import gdata.contacts.service
import gdata.calendar.service
import gdata.calendar_resource.client

#===============================================================================
# To do still... 
# (1) should really have try/catch around all writes to filesystem
# (2) should email me when done, with log file
# http://docs.python.org/library/email-examples.html
# (3) should subscribe _backup automatically to all system resources
# (4) Some kind of schedule for cleaning up old backups (meh)
# (5) clean up redundant service creation (e.g. apps service happens 2+ times)
# (6) Eventually... switch to oauth instead of this htpasswd nonsense
# (7) set the cwd in a non-stupid way
# (8) Get rid of hardcoded stuff
#===============================================================================

## Google Apps Clients/Services Connections ##

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



def main():
    #===============================================================================
    # ### CONSTANTS/GLOBALS ###
    #===============================================================================
    
    # skipNames: these names should not be backed up, and their passwords should not be touched
    skipNames = frozenset(['xxxx', 'xxxxx'])
    
    # globals...
    loginEmail = 'user@domain'
    loginPass = 'somepassword'
    loginDomain = 'domain'
    googleSource = loginDomain + ".backup.script"
    todaysDate = time.strftime('%Y-%m-%d')
    contactsSaveFile = todaysDate + "/00-contacts.csv"
    logSaveFile = todaysDate + "/00-log.txt"
    scpHtpasswdTo = 'user@host:/path/.htpasswd' 
    
    # if debug is true, errors go to the screen; there may be additional errors, too
    # if debug is false, everything is shunted to the log file 
    debug = False
    subprocess.call(['mkdir', todaysDate])
    
    if not debug: 
        # open the log file
        # dude, this seriously needs try/catch
        subprocess.call(['touch', logSaveFile])
        logOut = open(logSaveFile, 'a')
        
        # send all stdout and stderr to the log
        sys.stdout = logOut
        sys.stderr = logOut
    
    # start timer
    timeStart = time.time()
    print "Started at " + time.strftime('%Y-%m-%d %H:%M') + "\n"
    
    #===============================================================================
    # Back up current list of shared global contacts
    # super helpful: http://code.google.com/googleapps/domain/shared_contacts/gdata_shared_contacts_api_reference.html
    #===============================================================================
    gd_client = openGoogleContactsService(loginEmail, loginPass, googleSource)
    
    contactsOut = open(contactsSaveFile, 'w')
    
    def writeOutContacts(contactsFeed):
        for entry in contactsFeed.entry:
            if entry.title.text:
                contactsOut.write(entry.title.text)
                contactsOut.write(',')
                for email in entry.email:
                    contactsOut.write(email.address + '\n')
    
    # need to use a query rather than a straight feed to get around return limits
    contactsQuery = gdata.contacts.service.ContactsQuery(feed='http://www.google.com/m8/feeds/contacts/YOUR DOMAIN/full')
    contactsQuery.max_results = 1000
                    
    try:
        #contactsFeed = gd_client.GetContactsFeed('http://www.google.com/m8/feeds/contacts/YOUR DOMAIN/full')
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
        writeOutContacts(contactsFeed)
    
    contactsOut.close()
    if not debug:
        logOut.flush()
    
    #===============================================================================
    # Get full list of resources and subscribe _backup to all resources
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
    #    returned_calendar = calendar_service.InsertCalendarSubscription(calendar=a_calendar)
    #    
    #    #print returned_calendar
    #    returned_calendar.hidden = gdata.calendar.Hidden(value='false')
    #    returned_calendar.selected = gdata.calendar.Selected(value='true')
    #    updated_calendar = calendar_service.UpdateCalendar(calendar=returned_calendar)
    
    #===============================================================================
    # Get current list of users from Google
    #===============================================================================
    
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
    
    
    #===============================================================================
    # For each user, set htpasswd to tonight's random password
    #===============================================================================
    
    # get current .htpasswd file from server
    subprocess.call(['scp', scpHtpasswdTo, '.htpasswd'])
    
    # make a random password between 12 and 16 chars
    randMin = 12
    randMax = 16
    # note: issue: using random.sample means every character in the password is unique
    randomPassword = "".join(random.sample(string.letters+string.digits,random.randint(randMin,randMax)))
    
    # set new password for each user
    for i, a_user in enumerate(usersList):
        subprocess.call(["htpasswd", "-b", ".htpasswd", a_user.title.text, randomPassword])
        
    # upload back to server    
    subprocess.call(['scp', '.htpasswd', scpHtpasswdTo])
    
    #===============================================================================
    # Okay, now download a backup copy of the calendars for each user
    #===============================================================================
    
    
    def getUserCal(userName):
        #logOut.flush()
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
            newResponse = br.submit()
            #print newResponse.read()
        except:
            print "WARN: trouble downloading cal data for " + userName + ": " +  " at " + time.strftime('%H:%M') + ".\n"
            time.sleep(60)
            try:
                newResponse = br.submit()
                #print newResponse.read()
            except:
                print "FAIL: can't get cal data for " + userName + ": " +  " at " + time.strftime('%H:%M') + ".\n"
            else:
                print "OKAY - second try - retrieving cal data for user " + userName + " at " + time.strftime('%H:%M') + ".\n"
                br.retrieve('https://www.google.com/calendar/exporticalzip',fileNametoSave)   
        else:
            print "Retrieving cal data for user " + userName + " at " + time.strftime('%H:%M') + ".\n"
            br.retrieve('https://www.google.com/calendar/exporticalzip',fileNametoSave)
            
    ###### end def getUserCal
    
    for a_user in (usersList):
        userName = a_user.title.text
        br=mechanize.Browser()
        try:
            br.open('THIS IS THE URL TO YOUR LOGIN PAGE')
        except:
            print "WARN: Trouble with initial connect for " + userName + ": " +  " at " + time.strftime('%H:%M') + ".\n"
            time.sleep(60)
            try:
                br.open('THIS IS THE URL TO YOUR LOGIN PAGE')
            except:
                print "FAIL: gave up on initial connect for " + userName + ": " +  " at " + time.strftime('%H:%M') + ".\n"
                break
            
        br.select_form(name="theform")
        br['username']=userName
        br['password']=randomPassword
        
        # get SAML login response
        try:
            samlResponse = br.submit()
        except:
            print "WARN: can't get past SAML for " + userName + ": " +  " at " + time.strftime('%H:%M') + ".\n"
            time.sleep(60)
            try:
                samlResponse = br.submit()
            except:
                print "FAIL: can't get past SAML for " + userName + ": " +  " at " + time.strftime('%H:%M') + ".\n"
            else:
                print "OKAY: Login succeeded (second time) for " + userName + " at " + time.strftime('%H:%M') + ".\n"
                getUserCal(userName) 
        else:
            print "Login succeeded for " + userName + " at " + time.strftime('%H:%M') + ".\n"
            getUserCal(userName)
            
        #logOut.flush()
    
    #===============================================================================
    #  clean up....
    #===============================================================================
    totalSecondsElapsed = time.time() - timeStart
    hoursElapsed = int(totalSecondsElapsed / 3600)
    minutesElapsed = int((totalSecondsElapsed - hoursElapsed*3600) / 60)
    print 'Total time: %s hours, %s minutes (%s total seconds)' % (hoursElapsed, minutesElapsed, totalSecondsElapsed)
    
    if not debug:
        logOut.close()
# end def of main()


if __name__ == '__main__':
    main()

