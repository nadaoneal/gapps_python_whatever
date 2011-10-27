#!/usr/local/bin/python
#===============================================================================
#
# Currently: deletes items from shared address book if they're not owned by the 
# _backup account and if they match the user-submitted string; pauses for user confirmation
#
# Soon: should be able to read in a file of email addresses to match and delete
#===============================================================================

import time
import string
import subprocess
from subprocess import Popen, PIPE, STDOUT
import sys
import os
import re
from optparse import OptionParser

import atom
from ConfigParser import SafeConfigParser
import gdata.data
import gdata.apps.service
import gdata.contacts.service
import gdata.calendar.client



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
def returnFundCalsSet(calendar_client):
    calsFeed = calendar_client.GetAllCalendarsFeed()

    def returnEmailOnCal(calendar):
        tmp = calendar.id.text.replace("%40","@").replace("http://www.google.com/calendar/feeds/default/calendars/","")
        return tmp
    # end def returnEmailOnCal()
    
    return set([returnEmailOnCal(x) for x in calsFeed.entry])
    
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
        if entry.title.text is not None : 
            return True
        else:
            return False
        
    return filter(filterContacts, contactsFeed.entry)
        
# end def returnFundAddrsSet

def main():
   # get settings from external file
    config_file = 'settings.ini'
    parser = SafeConfigParser()
    parser.read(config_file)

    # set working directory
    # take default from settings or set something here
    #baseDir = parser.get('settings', 'baseDir')
    baseDir = "/opt/pytest"
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

    # add googleSource
    googleSource = loginDomain + ".abook.audit.script"
     
    # debug?
    debug = True     

    # matching calendar titles
    userString = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    
    usage = "usage: %prog [options] uni"
    parser = OptionParser(usage=usage)
    parser.add_option("-t", "--title", dest="userString", default=userString, metavar="TITLE", help="Delete all with titles matching your input string. Use quotes or backslashes to escape. Can take regexes.")
    (options, args) = parser.parse_args()
    userString = options.userString
    
    print "user String is " + userString


    #===============================================================================
    # Open Calendar Client, Contacts Service
    #===============================================================================

    calendar_client = gdata.calendar.client.CalendarClient(googleSource)
    calendar_client.auth_token = gdata.gauth.TwoLeggedOAuthHmacToken(consumerKey, consumerSecret, loginEmail)

    def openGoogleContactsService(loginEmail, loginPass, googleSource):
        # open Contacts Service connection
        contacts_service = gdata.contacts.service.ContactsService()
        contacts_service.email = loginEmail
        contacts_service.password = loginPass
        contacts_service.source = googleSource
        contacts_service.ProgrammaticLogin()
        return contacts_service
    # end def OpenGoogleContactsService()
    
    contacts_service = openGoogleContactsService(loginEmail, loginPass, googleSource)
    
    #===============================================================================
    # Listing of current calendars
    #===============================================================================

    currentCals = returnFundCalsSet(calendar_client)
    
    if False and debug:
        print "Current Calendars: \n"
        for i, a_calendar in enumerate(currentCals):
            print '\t%s. %s' % (i, a_calendar,)
            
    # get listing of all current shared abook entries
    currentAddrsList = returnFundAddrsList(contacts_service, loginDomain)        
    
    if debug:
        print "All addresses in address book:"
        for i, addrEntry in enumerate(currentAddrsList, start=1):
            print '\t%s. %s, %s' % (i, addrEntry.title.text, addrEntry.email[0].address)

   
    def eliminate(addrEntry, calSet, userString):
        for email in addrEntry.email:
                if email.address in calSet: 
                    # found in calendars - do not delete
                    return False 
                elif re.search(userString, addrEntry.title.text):
                    # not found, matches string - delete
                    return True
        # otherwise, do not delete
        return False

    addrsToDelete = [addr for addr in currentAddrsList if eliminate(addr, currentCals, userString)]

    print "Would delete these..."
    for i,addrEntry in enumerate(addrsToDelete):
        print '\t%s. %s, %s' % (i, addrEntry.title.text, addrEntry.email[0].address)
    
    if len(addrsToDelete) == 0 :
        print "(none)"
    
    deleteThem = False
    
    while True:
       userOK = raw_input('Proceed? (y):  ')
       if not userOK:
           break
       elif userOK.lower() == "y" or userOK.lower() == "y":
           deleteThem = True
           break
       else:
           break
    
    if deleteThem:
        for addrEntry in addrsToDelete:
            print 'Deleting %s...' % (addrEntry.title.text)
            contacts_service.DeleteContact(addrEntry.GetEditLink().href)
    else:
        print "Exiting..."
    

# end def of main()

if __name__ == '__main__':
  main()