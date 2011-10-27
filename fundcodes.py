#!/usr/local/bin/python
#===============================================================================
#
# fundcodes.py: populates "fund code" calendars with expenditure data
#                 from files located on a hostile server
#
# The script connects to an export directory on another server, which essentially
# has one sub-directory per calendar-which-needs-to-exist. Each sub-dir has
# an export file, where some lines in the files should turn into events in the calendar.
#
# The script generates a list of calendars that need to exist, and the list
# of currently existing calendars. Creates all calendars that do not currently
# exist, shares them with the domain, and populates the global shared address book with them. 
# This allows users to easily subscribe to these "private" calendars.
#
# Then, for each existing calendar, searches for data for that fund code. When data 
# is found, checks if there's already an event for that data, and if not, creates one.
#
#===============================================================================

#standard modules included with python
import time
from datetime import datetime, timedelta, date
import string
import re
import random
import subprocess
import sys
import os
from subprocess import Popen, PIPE, STDOUT

# you may need to install these modules
import mechanize
from pyparsing import makeHTMLTags,SkipTo
from ConfigParser import SafeConfigParser
import atom

# tested against gdata-2.0.14
# http://code.google.com/p/gdata-python-client/
# http://code.google.com/p/gdata-python-client/source/browse/samples/oauth/TwoLeggedOAuthExample.py
import gdata.apps.service
import gdata.calendar.client
import gdata.contacts.client
import gdata.contacts.service
import gdata.calendar.service
import gdata.calendar_resource.client
import gdata.gauth

########################
## Contacts Functions ##
########################

def addToContactsList(contacts_client, new_name, new_email, postUrl):
    new_contact = gdata.contacts.ContactEntry(title=atom.Title(text=new_name))
    new_contact.email.append(gdata.contacts.Email(address=new_email, primary='true', rel=gdata.contacts.REL_WORK))
    try: 
        contact_entry = contacts_client.CreateContact(new_contact,postUrl)
    except gdata.service.RequestError, e:
        print "Unable to create contact " + new_name
        print e
# end def addToContactsList


def openGoogleContactsService(loginEmail, loginPass, googleSource):
    # open Contacts Service connection
    contacts_service = gdata.contacts.service.ContactsService()
    contacts_service.email = loginEmail
    contacts_service.password = loginPass
    contacts_service.source = googleSource
    contacts_service.ProgrammaticLogin()
    return contacts_service
# end def OpenGoogleContactsService()



########################
## Calendar Functions ##
########################

def openGoogleCalendarService(loginEmail, loginPass, googleSource):
    # open Calendar Service connection
    calendar_service = gdata.calendar.service.CalendarService()
    calendar_service.email = loginEmail
    calendar_service.password = loginPass
    calendar_service.source = googleSource
    calendar_service.ProgrammaticLogin()
    return calendar_service
# end def OpenGoogleCalendarService()


# codesFilter looks returns only the codes that should be made into calendars
# currently, codes ending in E or EO
def codesFilter(item):
    if item is not None and re.search("^[0-9]*EO?$", item) : 
        return True
    else:
        return False
# end def codesFilter()

# returns a set
def returnFundCalsSet(calendar_client):
    calsFeed = calendar_client.GetAllCalendarsFeed()
    
    # there's also a weird bug where sometimes cal.title is None
    # so keeping this inefficiency for now until I figure that out
    def convertCalFeedtoNameSet(calsFeed):
        nameList = []
        for cal in calsFeed.entry:
            if cal.title is not None:
                nameList.append(cal.title.text)
        nameList = filter(codesFilter, nameList)
        return set(nameList)    
    # end def convertCalFeedtoNameSet()
    
    convertedCalsSet = convertCalFeedtoNameSet(calsFeed)
    return convertedCalsSet
# end def returnFundCalsSet()

# creates calendar, shares with the domain, and also adds to address book
def newFundCalendar(fundName, loginDomain, postUrl, calendar_client, contacts_service):
        # 1. create calendar
        calendar = gdata.calendar.data.CalendarEntry()
        calendar.title = atom.data.Title(text=fundName)
        calendar.hidden = gdata.calendar.data.HiddenProperty(value='false')
        print "Creating " + fundName
        try:
            new_calendar = calendar_client.InsertCalendar(new_calendar=calendar)
        except:
            print "Error creating calendar %s \n" % (fundName)
            return
        
        # 1.5 get the newly created calendar's acl list id
        # note: cal.id.text looks like:
        # http://www.google.com/calendar/feeds/default/owncalendars/full/apps.cul.columbia.edu_letters12345numbers%40group.calendar.google.com
        # we want : https://www.google.com/calendar/feeds/letters12345numbers%40group.calendar.google.com/acl/full/
        print "new calendar name is " + fundName
        calendar_id = new_calendar.id.text
        calendar_id = calendar_id.replace("http://www.google.com/calendar/feeds/default/calendars/","")
        print "new calendar id is " + calendar_id
        acl_list_id = "".join(["https://www.google.com/calendar/feeds/", calendar_id, "/acl/full/"])
        print "new acl list id is " + acl_list_id
        
        # 2. share calendar with the domain
        shareWithDomain = loginDomain + '_@domain.calendar.google.com'

        # ... need to retrieve current rule, then update it
        feed = calendar_client.GetCalendarAclFeed(acl_list_id)
        for i, a_rule in enumerate(feed.entry):
            if ( a_rule.scope.type == "domain" and a_rule.scope.value == loginDomain ):
                a_rule.scope = gdata.acl.data.AclScope(value=loginDomain, type="domain")
                roleValue = 'http://schemas.google.com/gCal/2005#%s' % ('read')
                a_rule.role = gdata.acl.data.AclRole(value=roleValue)
                try:
                    updated_rule = calendar_client.Update(a_rule)
                except gdata.service.RequestError, e:
                    print "Error setting ACL on %s \n %s" % (fundName, e[0]['body'])
                break
        
        # 3. append to contacts list
        new_name = "Fund Code " + fundName
        new_email = calendar_id.replace("%40","@")
        print "new email is " + new_email
        try:
            addToContactsList(contacts_service, new_name, new_email, postUrl)
        except gdata.service.RequestError, e:
            print "Error appending %s to Contacts List \n %s" % (fundName, e[0]['body'])
        
# end def NewFundCalendar()


# gets list of cals to populate
def getCalsToPopulate(calendar_client):
    calsFeed = calendar_client.GetAllCalendarsFeed()
    
    def codesFilterOnCal(item):
        if item is not None and item.title is not None and re.search("^[0-9]*EO?$", item.title.text) : 
            return True
        else:
            return False
    
    allCalsList = filter(codesFilterOnCal,calsFeed.entry)
    return allCalsList
# end def getCalsToPopulate()


# inserts an event, given a title, description, and date:
# date like YYYY-mm-dd
# calfeed like '/calendar/feeds/apps.cul.columbia.edu_letters123904830984numbers%40group.calendar.google.com/private/full'
def insertEvent(calendar_service, calFeed, title, description, date):
    event = gdata.calendar.CalendarEventEntry()
    event.title = atom.Title(text=title)
    event.content = atom.Content(text=description)
    event.when.append(gdata.calendar.When(start_time=date, end_time=date))
    try:
        new_event = calendar_service.InsertEvent(event, calFeed)
    except gdata.service.RequestError, e:
        print "Got RequestError: \n%s\n\n If 302, trying again with redirect...\n" % (e[0]['body'])
        matchObj = re.search(r'The document has moved \<A HREF="(.*)"\>here\</A\>',str(e)) 
        if matchObj:
            calFeed = matchObj.group(1)
            print "calFeed is now %s\n" % (calFeed)
        try:
            new_event = calendar_service.InsertEvent(event, calFeed)
        except:
            print "Another Google Error adding event after changed calFeed; skipping \n"
            print "Title is %s \n Date is %s \n Desc is \n %s \n XML is: %s \n\n" % (title, date, description, event)
    except:
        print "Some Google Error adding event; skipping \n"
        print "Title is %s \n Date is %s \n Desc is \n %s \n XML is: %s \n\n" % (title, date, description, event)
# end def insertEvent() 

def populateCalendar(calendar, hostConnect, fundsBaseDir, calendar_service, start_date, end_date, reminders=False):                
        calFeed = ''.join(['/calendar/feeds/', calendar.id.text.replace('http://www.google.com/calendar/feeds/default/calendars/', ''), '/private/full'])
        print "%s: %s" % (calendar.title.text, calFeed)
        
        calID = calendar.id.text.replace('http://www.google.com/calendar/feeds/default/calendars/', '').replace('%40','@')
        # find the text file
        cmd = ''.join(["ssh ", hostConnect, " 'ls -t ", fundsBaseDir,  \
                                   calendar.title.text, " | grep cumfile.xls'"])
        p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
        fileName = p.stdout.read()
        #fileName = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        
        # there may be no directory with this calendar name. If so, return 0
        # this happens when e.g. a code is discontinued
        # there was probably an error if what's returned contains a space
        if re.search(" ", fileName) :
            print "not found? " + fileName + "\n"
            return False
        
        # only need "expenditure" lines, if any
        cmd = ''.join(["ssh ", hostConnect, " 'grep expenditure ", fundsBaseDir, \
                        calendar.title.text, "/", fileName, "'"])
        p =  subprocess.Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
        fileContent = p.stdout.readlines()
        # read line by line and then split each line on the tab char

        # get all current events from the calendar
        # this is using the calendar service instead of the client
        query = gdata.calendar.service.CalendarEventQuery(calID, 'private', 'full')
        query.start_min = start_date
        query.start_max = end_date 
        query.max_results = 9999
        try:
            feed = calendar_service.CalendarQuery(query)
        except gdata.service.RequestError, e:
            print "failed first attempt to get event list of" + calendar.title.text
            print e[0]['body']
            time.sleep(20)
            try:
                feed = calendar_service.CalendarQuery(query)
            except gdata.service.RequestError, e:
                print "giving up on " + calendar.title.text
                print e[0]['body']
                return False
            
        
        def returnEventDesc(event):
            returnText = "xxxxxxxxzzzzzzzzz-no-match"
            if event is not None and event.content is not None and event.content.text is not None:
                returnText = event.content.text.rstrip()
            return returnText
        
        googleEventSet = set(map(returnEventDesc, feed.entry))

        for line in (fileContent):
            eventData = line.split('\t')
            eventDateRaw = eventData[2]
            eventDate = '-'.join([eventDateRaw[0:4], eventDateRaw[4:6], eventDateRaw[6:8]])
            # sometimes there's an extraneous "PAYMENT RECORD" in the title; chop it
            # also replace final \t and final ., if exists
            journal = eventData[3].replace("PAYMENT RECORD", "").replace("\[\]$","").replace("\.","")
            eventTitle = ' '.join([journal, eventData[8]])
            
            isNegative = (float(eventData[8]) < 0)
            isBadTitle = isNegative and (bool(re.search("^COMMITMENTS",eventTitle)) or bool(re.search("^INTERNAL USE ONLY",eventTitle)))
            
            # don't add events if they have "bad titles" or if they're already entered 
            if line.rstrip() in googleEventSet or isBadTitle:
                #pass
                print 'Skipping %s: %s on %s' % (calendar.title.text, eventTitle, eventDate)    
            else:
                print 'Adding %s: %s on %s' % (calendar.title.text, eventTitle, eventDate)
                try:
                    pass
                    insertEvent(calendar_service, calFeed, eventTitle, line, eventDate)
                except gdata.service.RequestError, e:
                    print "Error adding event; skipping remainder"
                    print e[0]['body']
                    return False   
        
            # don't add reminders for negative amounts
            if reminders and not isNegative:
                    #print "adding reminder:"
                    origDate = date(int(eventDateRaw[0:4]), int(eventDateRaw[4:6]), int(eventDateRaw[6:8]))
                    
                    # will expire a year from now
                    willExpireOn = origDate + timedelta(days=365)
                    willExpireOnFormatted = willExpireOn.strftime("%m/%d/%Y")
                    
                    # four Months reminder event 
                    # when you have 5 months left to renew
                    fourMonths = origDate + timedelta(days=212)
                    fourMonthsFormatted = fourMonths.strftime("%Y-%m-%d")
                    fmEventTitle = ' '.join(["renew", eventTitle, "by", willExpireOnFormatted])
                    fmDescription = ' '.join(["(five months reminder)", line])
                    if fmDescription.rstrip() in googleEventSet:
                        # BUG! Future events not in this set
                        pass
                        #print '\tSkipping %s: %s on %s' % (calendar.title.text, fmEventTitle, fourMonthsFormatted)
                    else:
                        print '\tAdding %s: %s on %s' % (calendar.title.text, fmEventTitle, fourMonthsFormatted)
                        try:
                            pass
                            insertEvent(calendar_service, calFeed, fmEventTitle, fmDescription, fourMonthsFormatted)
                        except gdata.service.RequestError, e:
                            print "Error adding event; skipping remainder"
                            print e[0]['body']
                            return False  
                    
                    # "eight Months" reminder event
                    # when you have 3 months left to renew
                    eightMonths = origDate + timedelta(days=274)
                    eightMonthsFormatted = eightMonths.strftime("%Y-%m-%d")
                    emEventTitle = ' '.join(["renew", eventTitle, "by", willExpireOnFormatted])
                    emDescription = ' '.join(["(three months reminder)", line])                   
                    if emDescription.rstrip() in googleEventSet:
                        # BUG! Future events not in this set
                        pass
                        #print '\tSkipping %s: %s on %s' % (calendar.title.text, emEventTitle, eightMonthsFormatted)
                    else:
                        print '\tAdding %s: %s on %s' % (calendar.title.text, emEventTitle, eightMonthsFormatted)
                        try:
                            pass
                            insertEvent(calendar_service, calFeed, emEventTitle, emDescription, eightMonthsFormatted)
                        except gdata.service.RequestError, e:
                            print "Error adding event; skipping remainder"
                            print e[0]['body']
                            return False                           
          # end iterating over line in file content
           
# end def populateCalendar()




## end Calendar Functions ##

                                            #############################
                                            ##   ~~     main!    ~~    ##
                                            #############################

def main():
    #===============================================================================
    # Settings
    #===============================================================================
    # get settings from external file
    config_file = '/opt/fundcodes/settings.ini'
    parser = SafeConfigParser()
    parser.read(config_file)

    # set working directory
    # take default from settings or set something here
    baseDir = parser.get('settings', 'baseDir')
    #baseDir = "/opt/pytest"
    os.chdir(baseDir)
    
    # login info for non-oauth apis like provisioning...
    loginUser = parser.get('settings', 'loginUser')
    loginPass = parser.get('settings', 'loginPass')
    loginDomain = parser.get('settings', 'loginDomain')
    loginEmail = loginUser + '@' + loginDomain
    loginURL = 'http://' + loginDomain
    
    # contacts stuff
    postUrl = "".join(["http://www.google.com/m8/feeds/contacts/",loginDomain,"/full"])
    
    # oath stuff
    consumerKey = loginDomain
    consumerSecret = parser.get('settings', 'oauth_secret')
    
    # logging info
    todaysDate = time.strftime('%Y-%m-%d')
    logSaveFile = todaysDate + "-fundcodes.log"
    scpHtpasswdTo = parser.get('settings', 'scpHtpasswdTo') 
    
    # add googleSource
    googleSource = loginDomain + ".subscribe.script"
    
    # data files location
    hostConnect = 'nco2104@mimolette.cc.columbia.edu' 
    fundsBaseDir = '/wwws/data/cu/libraries/inside/clio/statistics/acquisitions/fundcode/funds9/'

    # funds for which fiscal year?
    # this limits your query on the calendar when you check for previously created events
    # note: if you're adding reminders, add a year to the latter date
    fiscalYearStart = "2011-06-30"
    fiscalYearEnd = "2013-07-01"
    
    # add in reminders?
    reminders = True
    
    #===============================================================================
    # Logging / Time... 
    #===============================================================================

    debug = True
    
    subprocess.call(['touch', logSaveFile], stderr=subprocess.STDOUT)
    logOut = open(logSaveFile, 'a')
    
    sys.stdout = logOut
    sys.stderr = logOut
    #subprocess.STDOUT = logOut
    
    # start timer
    timeStart = datetime.now()
    print "Started at " + timeStart.strftime("%Y-%m-%d %H:%M:%S") + "\n"
    
    #===============================================================================
    # Open Calendar Client, Contacts Service
    #===============================================================================

    calendar_client = gdata.calendar.client.CalendarClient(googleSource)
    calendar_client.auth_token = gdata.gauth.TwoLeggedOAuthHmacToken(consumerKey, consumerSecret, loginEmail)

    contacts_service = openGoogleContactsService(loginEmail, loginPass, googleSource)
    calendar_service = openGoogleCalendarService(loginEmail, loginPass, googleSource)
 
    #===============================================================================
    # What calendars exist now?
    #===============================================================================
    
    # get listing of all current calendars that look like "Fund Code X"
    currentCals = returnFundCalsSet(calendar_client)
    
    # this only gets printed to screen if debugging
    if False and debug:
        print "Current Calendars: \n"
        for i, a_calendar in enumerate(currentCals):
            print '\t%s. %s' % (i, a_calendar,)
    
    #===============================================================================
    # What calendars should exist?
    #===============================================================================    
    
    # get listing of all funds on disk that look like "*EO" or "*E"
    cmd = "".join(["ssh ", hostConnect, " 'ls ", fundsBaseDir, "'"])
    p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
    output = p.stdout.read()
    #output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)

    # now filter this output
    fundsList = output.split('\n')
    fundsList = filter(codesFilter,fundsList)
    fundsSet = set(fundsList)

    # this only gets printed to screen, if ever
    if False and debug:
        print "\n\n Current Codes: \n"
        for i, mrstring in enumerate(fundsList):
            print '\t%s. %s' % (i, mrstring,)

    #===============================================================================
    # Create the difference
    #===============================================================================  

    toCreate = fundsSet - currentCals
    
    # note which new calendars are getting created
    print "\n\n To Create: \n"
    for i, mrstring in enumerate(toCreate):
        print '\t%s. %s' % (i, mrstring,)

    ## Now, create all the calendars that need creating    
    for fundName in toCreate:
        newFundCalendar(fundName, loginDomain, postUrl, calendar_client, contacts_service)

    #===============================================================================
    # Populate calendars with events
    #===============================================================================  

    ## Get new list of current calendars (in case there were errors in creating)
    calsToPopulate = getCalsToPopulate(calendar_client)
    
    ## Next, populate each calendar with new events
    for calendar in calsToPopulate:
        populateCalendar(calendar, hostConnect, fundsBaseDir, calendar_service, fiscalYearStart, fiscalYearEnd, reminders)

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