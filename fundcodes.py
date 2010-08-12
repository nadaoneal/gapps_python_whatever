#!/usr/bin/python
#===============================================================================
#
# fundcodes.py: populates "fund code" calendars with expenditure data
#                 from files located on a hostile server
#
# There are a couple of crazy-seeming decisions in this program, mostly relating
# to the way that data is extracted out of the "cumfile.xls" files (actually
# tab-delimited files). Ssh and grep and wtf?? Just ignore all that.
#
# For the rest - script gets a list of calendars that need to exist, and the list
# of currently existing calendars. Creates all calendars that do not currently
# exist, shares them with the domain, and populates the global shared address book with them. 
# This allows users to easily subscribe to these "private" calendars.
#
# Then, for each existing calendar, searches for data for that fund code. When data 
# is found, checks if there's already an event for that data, and if not, creates one.
#
#===============================================================================

import time
import string
import random
import subprocess
from subprocess import Popen, PIPE, STDOUT
import sys
import re

import mechanize
from pyparsing import makeHTMLTags,SkipTo

import atom
import gdata.data
import gdata.apps.service
import gdata.contacts.service
import gdata.calendar.service
import gdata.calendar_resource.client

## basic logger ##
## no longer in use - got bored of passing logOut to every function
## now send everything to stdout, but redirect stdout to log
def logger(logOut, message):
    logOut.write(message + "\n")
    logOut.flush()
# end def logger()

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


## Google Apps Operations ##
# adds calendar addr to global address book
def addToContactsList(contacts_service, new_name, new_email, postUrl):
    new_contact = gdata.contacts.ContactEntry(title=atom.Title(text=new_name))
    new_contact.email.append(gdata.contacts.Email(address=new_email, primary='true', rel=gdata.contacts.REL_WORK))
    try: 
        contact_entry = contacts_service.CreateContact(new_contact,postUrl)
    except gdata.service.RequestError, e:
        print "Unable to create contact " + new_name
        print e
# end def addToContactsList
    
# creates calendar, shares with the domain, and also adds to address book
def newFundCalendar(fundName, loginDomain, postUrl, calendar_service, contacts_service):
        # 1. create calendar
        calendar = gdata.calendar.CalendarListEntry()
        calendar.title = atom.Title(text=fundName)
        calendar.hidden = gdata.calendar.Hidden(value='false')
        print "Creating " + fundName
        new_calendar = calendar_service.InsertCalendar(new_calendar=calendar)
        
        # 1.5 get the newly created calendar's acl list id
        # note: cal.id.text looks like:
        # http://www.google.com/calendar/feeds/default/owncalendars/full/apps.cul.columbia.edu_letters12345numbers%40group.calendar.google.com
        # we want : https://www.google.com/calendar/feeds/letters12345numbers%40group.calendar.google.com/acl/full/
        print "calendar name is " + fundName
        calendar_id = new_calendar.id.text
        calendar_id = calendar_id.replace("http://www.google.com/calendar/feeds/default/owncalendars/full/","")
        print "calendar id is " + calendar_id
        acl_list_id = "".join(["https://www.google.com/calendar/feeds/", calendar_id, "/acl/full/"])
        print "acl list id is " + acl_list_id
        
        # 2. share calendar with the domain
        shareWithDomain = loginDomain + '_@domain.calendar.google.com'
        rule = gdata.calendar.CalendarAclEntry()
        rule.scope = gdata.calendar.Scope(value=shareWithDomain, scope_type="user")
        roleValue = 'http://schemas.google.com/gCal/2005#%s' % ('read')
        rule.role = gdata.calendar.Role(value=roleValue)
        aclUrl = acl_list_id
        returned_rule = calendar_service.InsertAclEntry(rule, aclUrl)
        
        # 3. append to contacts list
        new_name = "Fund Code " + fundName
        new_email = calendar_id.replace("%40","@")
        print "new email is " + new_email
        addToContactsList(contacts_service, new_name, new_email, postUrl)
# end def NewFundCalendar()

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
    except:
        print "Some Google Error adding event %s on %s; skipping" % (event, date)
# end def insertEvent() 

def populateCalendar(calendar, hostConnect, fundsBaseDir, calendar_service, start_date, end_date):
        print calendar.title.text
        calFeed = ''.join(['/calendar/feeds/', calendar.id.text.replace('http://www.google.com/calendar/feeds/default/allcalendars/full/', ''), '/private/full'])
        print calFeed
        calID = calendar.id.text.replace('http://www.google.com/calendar/feeds/default/allcalendars/full/', '').replace('%40','@')
        # find the text file
        cmd = ''.join(["ssh ", hostConnect, " 'ls -t ", fundsBaseDir,  \
                                   calendar.title.text, " | grep cumfile.xls'"])
        p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
        fileName = p.stdout.read()
        #print cmd
        #print fileName
        
        # there may be no directory with this calendar name. If so, return 0
        # this happens when e.g. a code is discontinued
        # there was probably an error if what's returned contains a space
        if re.search(" ", fileName) :
            print "not found? " + fileName + "\n"
            return False
        
        # only need "expenditure" lines, if any
        cmd = ''.join(["ssh ", hostConnect, " 'grep expenditure ", fundsBaseDir, \
                        calendar.title.text, "/", fileName, "'"])
        p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
        fileContent = p.stdout.readlines()
        # read line by line and then split each line on the tab char

        # get all current events from the calendar
        query = gdata.calendar.service.CalendarEventQuery(calID, 'private', 'full')
        query.start_min = start_date
        query.start_max = end_date 
        query.max_results = 500
        feed = calendar_service.CalendarQuery(query)
        
        def returnEventDesc(event):
            return event.content.text.rstrip()
        
        googleEventSet = set(map(returnEventDesc, feed.entry))

        for line in (fileContent):
            eventData = line.split('\t')
            eventDateRaw = eventData[2]
            eventDate = '-'.join([eventDateRaw[0:4], eventDateRaw[4:6], eventDateRaw[6:8]])
            # sometimes there's an extraneous "PAYMENT RECORD" in the title; chop it
            # also replace final \t and final ., if exists
            journal = eventData[3].replace("PAYMENT RECORD", "").replace("\[\]$","").replace("\.","")
            eventTitle = ' '.join([journal, eventData[8]])
           
            if line.rstrip() in googleEventSet:
                print 'Skipping %s: %s on %s' % (calendar.title.text, eventTitle, eventDate) 
            else:
                print 'Adding %s: %s on %s' % (calendar.title.text, eventTitle, eventDate)
                try:
                    insertEvent(calendar_service, calFeed, eventTitle, line, eventDate)
                except gdata.service.RequestError, e:
                    print "Error adding event; skipping remainder"
                    print e
                    return False                       
           
# end def populateCalendar()
        
## helpers and filters for main() ##

## codesFilter v. codesFilterOnCal is a bit of an embarrassment, yeah. ha.

# codesFilter looks returns only the codes that should be made into calendars
# currently, codes ending in E or EO
def codesFilter(item):
    if re.search("^[0-9]*EO?$", item) : 
        return True
    else:
        return False
# end def codesFilter()

# codesFilterOnCal is taking in calendar feed entry objects rather than strings
# looks returns only the codes that should be made into calendars
# currently, codes ending in E or EO
def codesFilterOnCal(item):
    if re.search("^[0-9]*EO?$", item.title.text) : 
        return True
    else:
        return False
# end def codesFilterOnCal()


def returnFundCalsSet(calendar_service):
    calsFeed = calendar_service.GetAllCalendarsFeed()
    
    # this is crappy, originally because I didn't realize that 
    # calFeed.entry is the iterable object, not calFeed
    # I would fix this, but there's also a weird bug where sometimes cal.title is None
    # so keeping this inefficiency for now until I figure that out
    def convertCalFeedtoNameSet(calsFeed):
        nameList = []
        for cal in calsFeed.entry:
            if cal.title is not None:
                nameList.append(cal.title.text)
            else:
                print "cal title was None..."
                print cal.title
        nameList = filter(codesFilter, nameList)
        return set(nameList)    
    # end def convertCalFeedtoNameSet()
    
    convertedCalsSet = convertCalFeedtoNameSet(calsFeed)
    return convertedCalsSet
# end def returnFundCalsSet()

def getCalsToPopulate(calendar_service):
    calsFeed = calendar_service.GetAllCalendarsFeed()
    allCalsList = filter(codesFilterOnCal,calsFeed.entry)
    return allCalsList
# end def getCalsToPopulate()

def main():
    # domain/login details...
    loginEmail = 'some_admin@your_domain'
    loginPass = 'that_acct_pw'
    loginDomain = 'your_domain'
    postUrl = "".join(["http://www.google.com/m8/feeds/contacts/",loginDomain,"/full"])
    googleSource = loginDomain + '.fundcodes'
    
    # getting-the-funds-list details
    hostConnect = 'your_acct@the_hostile_server' 
    fundsBaseDir = '/parent/dir/of/the/files'
    
    # funds for which fiscal year?
    # this limits your query on the calendar when you check for previously created events
    fiscalYearStart = "2010-06-30"
    fiscalYearEnd = "2011-07-01"
        
    # logging details
    todaysDate = time.strftime('%Y-%m-%d')
    logSaveFile = todaysDate + "/00-log.txt"
    
    # Do you want messages to go to the screen (debug=True),
    # or to the log file? (debug=False)
    # debug also turns on some additional info
    debug = True
    
    # open the log file, assuming you're not in debug mode
    # send everything to the log file
    # dude, this seriously needs try/catch
    # why was I born so lazy?
    if not debug:
        subprocess.call(['mkdir', todaysDate])
        subprocess.call(['touch', logSaveFile])
        logOut = open(logSaveFile, 'a')
        sys.stdout = logOut
        sys.stderr = logOut
    
    # start timer
    timeStart = time.time()
    print "Started at " + time.strftime('%Y-%m-%d %H:%M')
    
    # open calendar and contacts services
    calendar_service = openGoogleCalendarService(loginEmail, loginPass, googleSource)
    contacts_service = openGoogleContactsService(loginEmail, loginPass, googleSource)
        
    # get listing of all current calendars that look like "Fund Code X"
    currentCals = returnFundCalsSet(calendar_service)
    
    # this only gets printed to screen, if debugging
    if debug:
        print "Current Calendars: \n"
        for i, a_calendar in enumerate(currentCals):
            print '\t%s. %s' % (i, a_calendar,)
    
    # get listing of all funds on disk that look like "*EO" or "*E"
    cmd = "".join(["ssh ", hostConnect, " 'ls ", fundsBaseDir, "'"])
    p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
    output = p.stdout.read()

    # now filter this output
    fundsList = output.split('\n')
    fundsList = filter(codesFilter,fundsList)
    fundsSet = set(fundsList)

    # this only gets printed to screen, if ever
    if False & debug:
        print "\n\n Current Codes: \n"
        for i, mrstring in enumerate(fundsList):
            print '\t%s. %s' % (i, mrstring,)

    toCreate = fundsSet - currentCals
    
    # note which new calendars are getting created
    print "\n\n To Create: \n"
    for i, mrstring in enumerate(toCreate):
        print '\t%s. %s' % (i, mrstring,)
    
    ## Now, create all the calendars that need creating    
    for fundName in toCreate:
        try:
            newFundCalendar(fundName, loginDomain, postUrl, calendar_service, contacts_service)
        except gdata.service.RequestError, e: 
            #{'status': 403, 'body': 'Not enough quota to create a calendar.', 'reason': 'Forbidden'}
            print "Unable to create calendar " + fundName + ": "
            print e
            # skip the rest because 90% of the time this is because you ran out of quota
            print "Skipping create on remaining calendars"
            break
        
    ## Get new list of current calendars (in case there were errors in creating)
    calsToPopulate = getCalsToPopulate(calendar_service)
    
    ## Next, populate each calendar with new events
    for calendar in calsToPopulate:
        populateCalendar(calendar, hostConnect,fundsBaseDir, calendar_service, fiscalYearStart, fiscalYearEnd)
    
    #### clean up...
    totalSecondsElapsed = time.time() - timeStart
    hoursElapsed = int(totalSecondsElapsed / 3600)
    minutesElapsed = int((totalSecondsElapsed - hoursElapsed*3600) / 60)
    print "Total time: %s hours, %s minutes (%s total seconds)\n\n" % (hoursElapsed, minutesElapsed, totalSecondsElapsed)
    if not debug:
        logOut.close()

# end def of main()


if __name__ == '__main__':
  main()
