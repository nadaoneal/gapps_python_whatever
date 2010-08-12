#!/usr/bin/python
#===============================================================================
#
# Currently: just cleans up a mess I made in the shared address book
# with the fundcodes.py script (there were a pile of addrbook entries pointing
# to deleted calendars)
#
# Future dreams for this script...
# 
# it could look in your google apps for your domain shared addressbook
# and delete any addresses that match certain criteria:
# - match a regex on name
# - and match a regex on address
# - and, optionally, do not have an associated calendar in a given account
#
# BIG LIMITATION: You cannot, I don't think, search for user-created calendars
# in any account other than the account that you're using to log in with.
# So you want to be careful not to do something like "delete all addresses not 
# associated with some calendar" because you'll end up deleting addresses that
# are associated with calendars you cannot see.
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
import gdata.contacts.service
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
def addToContactsList(contacts_service, new_name, new_email, postUrl, logOut):
    new_contact = gdata.contacts.ContactEntry(title=atom.Title(text=new_name))
    new_contact.email.append(gdata.contacts.Email(address=new_email, primary='true', rel=gdata.contacts.REL_WORK))
    try: 
        contact_entry = contacts_service.CreateContact(new_contact,postUrl)
    except gdata.service.RequestError, e:
        print "Unable to create contact " + new_name
        print e
# end def addToContactsList
    
# filters out calfeed to just "Fund Cals" calendars and 
# returns a set of just their email addresses
def returnFundCalsSet(calendar_service):
    calsFeed = calendar_service.GetAllCalendarsFeed()
    
    def codesFilterOnCal(item):
        if re.search("^[0-9]*EO?$", item.title.text) : 
            return True
        else:
            return False
    # end def codesFilterOnCal()
    
    def returnEmailOnCal(calendar):
        tmp = calendar.id.text.replace("%40","@").replace("http://www.google.com/calendar/feeds/default/allcalendars/full/","")
        return tmp
    # end def returnEmailOnCal()
    
    return set([returnEmailOnCal(x) for x in calsFeed.entry if codesFilterOnCal(x)])
    
# end def returnFundCalsSet()

def returnFundAddrsList(contacts_service, loginDomain):
    domainFeed = 'http://www.google.com/m8/feeds/contacts/' + loginDomain + '/full'
    contactsQuery = gdata.contacts.service.ContactsQuery(feed=domainFeed)
    contactsQuery.max_results = 1000
    try:
        contactsFeed = contacts_service.GetContactsFeed(contactsQuery.ToUri())
    except gdata.service.RequestError:
        print "Failed to get contacts feed on first try"
        sleep(20)
        try: 
           contactsFeed = contacts_service.GetContactsFeed(contactsQuery.ToUri())
        except gdata.service.RequestError:
            print "Failed to get contacts feed on second try"
            return []
    
    def filterContacts(entry):
        if entry.title.text is not None and re.search("^Fund Code [0-9]*EO?$", entry.title.text) : 
            return True
        else:
            return False
        
    return filter(filterContacts, contactsFeed.entry)
        
# end def returnFundAddrsSet

def main():
    # domain/login details...
    loginEmail = 'admin@yourdomain'
    loginPass = 'password'
    loginDomain = 'yourdomain'
    googleSource = loginDomain + '.clean.stupid.addrbook'
    debug = True
  
    # logging details
    todaysDate = time.strftime('%Y-%m-%d')
    logSaveFile = todaysDate + "/00-log.txt"

    # send all stdout and stderr to the log (unless debug)
    if not debug:
        # open the log file
        # dude, this seriously needs try/catch
        # why was I born so lazy?
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
    
    if False and debug:
        print "Current Calendars: \n"
        for i, a_calendar in enumerate(currentCals):
            print '\t%s. %s' % (i, a_calendar,)
            
    # get listing of all current shared abook entries that look like "Fund Code X"
    currentAddrsList = returnFundAddrsList(contacts_service, loginDomain)        
    
    if False and debug:
        print "Current Addresses:"
        for i, addrEntry in enumerate(currentAddrsList):
            print '\t%s. %s' % (i, addrEntry.title.text)

    def eliminate(addrEntry, calSet):
        for email in addrEntry.email:
                if email.address in calSet:
                    # if found, do not eliminate
                    return False
        # if not found, will eliminate
        return True

    addrsToDelete = [addr for addr in currentAddrsList if eliminate(addr, currentCals)]

    print "Will be deleting these..."
    for i,addrEntry in enumerate(addrsToDelete):
        print '\t%s. %s, %s' % (i, addrEntry.title.text, addrEntry.email.pop().address)
    
    for addrEntry in addrsToDelete:
        print 'Deleting %s...' % (addrEntry.title.text)
        contacts_service.DeleteContact(addrEntry.GetEditLink().href)
    
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
