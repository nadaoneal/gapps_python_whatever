#!/usr/local/bin/python
#===============================================================================
#
# An extension of empty_cals, it just deletes selected events from calendars you specify
# (Obviously not an "extension" in the OOP sense. Business logic is hard-coded.)
#
#===============================================================================

import time
import string
import subprocess
from subprocess import Popen, PIPE, STDOUT
import sys
import re

import atom
import gdata.data
import gdata.apps.service
import gdata.calendar.service
import gdata.calendar_resource.client

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

def getMatchingCalIDs(calendar_service, calsToEmpty, calsPatternToEmpty):
    def returnEmailOnCal(calendar):
        tmp = calendar.id.text.replace("%40","@").replace("http://www.google.com/calendar/feeds/default/allcalendars/full/","")
        return tmp
    # end def returnEmailOnCal()
    
    def isACalToEmpty(item):
        debug = True
        if item.title is not None and \
                (item.title.text in calsToEmpty or \
                 re.search(calsPatternToEmpty, item.title.text)) : 
            if debug:
                print "going to delete from " + item.title.text
            return True
        else:
            if debug:
                print "skipping cal " + item.title.text
            return False
    # end def matchCalsToEmpty()
    
    # now get the calsFeed and do a list comprehension
    calsFeed = calendar_service.GetAllCalendarsFeed()
    return [returnEmailOnCal(x) for x in calsFeed.entry if isACalToEmpty(x)] 
# end def getMatchingCalIDs()

def deleteCheck(calendar_service, event, debug=False):
    eventTitle = event.title.text.rstrip()
    eventDesc = event.content.text.rstrip()
    eventData = eventDesc.split('\t')
    
    isNegative = (float(eventData[8]) < 0)
    isReminder = bool(re.search("^renew",eventTitle))
    isBadTitle = isNegative and (bool(re.search("^COMMITMENTS",eventTitle)) or bool(re.search("^INTERNAL USE ONLY",eventTitle)))
 
    def loopTry(calendar_service, eventEditLink):
        trying = True
        attempts = 0
        sleep_secs = 1
        gsessionid = ''
        while trying:
            trying = False
            attempts += 1
            try:
                calendar_service.DeleteEvent(eventEditLink + gsessionid)
            except gdata.service.RequestError as inst:
                thing = inst[0] 
                if thing['status'] == 302 and attempts < 8:
                    trying = True
                    gsessionid=thing['body'][ thing['body'].find('?') : thing['body'].find('">here</A>')]
                    print 'Received redirect - retrying in', sleep_secs, 'seconds with', gsessionid
                    time.sleep(sleep_secs)
                    sleep_secs *= 2
                else:
                    print 'too many RequestErrors, giving up'
 
    if (isNegative and isReminder):
        if debug:
            print "Would delete neg reminder " + eventDesc
        else:
            print "deleting neg reminder " + eventDesc[0:40] + " " +  eventData[8]
            loopTry(calendar_service, event.GetEditLink().href)
            #calendar_service.DeleteEvent(event.GetEditLink().href)
    elif (isNegative and isBadTitle):
        if debug:
            print "Would delete neg bad title " + eventDesc
        else:
            print "deleting neg bad title " + eventDesc[0:40] + " " + eventData[8]
            loopTry(calendar_service, event.GetEditLink().href)
            #calendar_service.DeleteEvent(event.GetEditLink().href)
    elif debug:
        print "skip " + str(isNegative) + str(isReminder) + str(isBadTitle) + " " + eventDesc
        
# end def deleteCheck()

def main():
    # domain/login details...
    loginEmail = 'USER@domain'
    loginPass = 'PASSWORD'
    loginDomain = 'DOMAIN'
    googleSource = loginDomain + '.empty.calendars'
    debug = True
  
    # which calendars do you want to empty?
    # calsPattern and calsToEmpty match on the calendar title
    # kludge: set the pattern to something impossible to just use the set; 
    #     make the set empty, or contain pattern matches only, to just use the pattern
    calsPatternToEmpty = "^[0-9]*EO?$"
    #calsToEmpty = frozenset(['2462E', '2462EO', '2463E', '2463EO', '2464E', \
    #                              '2464EO', '2465E', '2465EO', '2377E', '2377EO'])
    calsToEmpty = frozenset([])

    # what date range should be emptied?
    # sorry, this is required
    # Also NOTE: if you have more than 9999 events, you will need to run this program more than once
    start_date = "2011-05-01"
    end_date = "2012-12-31"
  
    # start timer
    timeStart = time.time()
    print "Started at " + time.strftime('%Y-%m-%d %H:%M')
    
    # open calendar and contacts services
    calendar_service = openGoogleCalendarService(loginEmail, loginPass, googleSource)
    
    # get listing of calendar objects for calendars you want to empty
    matchingCalIDs = getMatchingCalIDs(calendar_service, calsToEmpty, calsPatternToEmpty)
    
    # for each calendar, get a listing of events, and delete all of them

    for calID in matchingCalIDs:
        # get feed of current events from the calendar
        if debug:
            print "In Calendar " + calID
        query = gdata.calendar.service.CalendarEventQuery(calID, 'private', 'full')
        query.start_min = start_date
        query.start_max = end_date 
        query.max_results = 9999
        try:
            feed = calendar_service.CalendarQuery(query)
        except gdata.service.RequestError, e:
            print "failed first attempt to get event list of" + calendar.title.text
            print e
            sleep(20)
            try:
                feed = calendar_service.CalendarQuery(query)
            except gdata.service.RequestError, e:
                print "giving up on " + calendar.title.text
                print e
                return False
    
        # now iterate over the feed and delete each event
        # could also chunk this into several batch requests, viz:
        # http://code.google.com/apis/calendar/data/1.0/developers_guide_python.html#batch
        for event in feed.entry:
            deleteCheck(calendar_service, event, debug)

    #### clean up...
    totalSecondsElapsed = time.time() - timeStart
    hoursElapsed = int(totalSecondsElapsed / 3600)
    minutesElapsed = int((totalSecondsElapsed - hoursElapsed*3600) / 60)
    print "Total time: %s hours, %s minutes (%s total seconds)\n\n" % (hoursElapsed, minutesElapsed, totalSecondsElapsed)
    

# end def of main()

if __name__ == '__main__':
  main()
