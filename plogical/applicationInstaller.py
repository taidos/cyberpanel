#!/usr/local/CyberCP/bin/python
import os, sys

sys.path.append('/usr/local/CyberCP')
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CyberCP.settings")
django.setup()
import threading as multi
from plogical.CyberCPLogFileWriter import CyberCPLogFileWriter as logging
import subprocess
from plogical.vhost import vhost
from websiteFunctions.models import ChildDomains, Websites
from plogical import randomPassword
from plogical.mysqlUtilities import mysqlUtilities
from databases.models import Databases
from plogical.installUtilities import installUtilities
import shutil
from plogical.processUtilities import ProcessUtilities
from random import randint

class ApplicationInstaller(multi.Thread):

    LOCALHOST = 'localhost'

    def __init__(self, installApp, extraArgs):
        multi.Thread.__init__(self)
        self.installApp = installApp
        self.extraArgs = extraArgs
        if extraArgs != None:
            try:
                self.tempStatusPath = self.extraArgs['tempStatusPath']
            except:
                pass

    def run(self):
        try:

            if self.installApp == 'wordpress':
                self.installWordPress()
            elif self.installApp == 'joomla':
                self.installJoomla()
            elif self.installApp == 'prestashop':
                self.installPrestaShop()
            elif self.installApp == 'magento':
                self.installMagento()
            elif self.installApp == 'convertDomainToSite':
                self.convertDomainToSite()
            elif self.installApp == 'updatePackage':
                self.updatePackage()
            elif self.installApp == 'mautic':
                self.installMautic()

        except BaseException as msg:
            logging.writeToFile(str(msg) + ' [ApplicationInstaller.run]')

    def installMautic(self):
        try:

            admin = self.extraArgs['admin']
            domainName = self.extraArgs['domainName']
            home = self.extraArgs['home']
            tempStatusPath = self.extraArgs['tempStatusPath']
            self.tempStatusPath = tempStatusPath
            username = self.extraArgs['username']
            password = self.extraArgs['password']
            email = self.extraArgs['email']

            FNULL = open(os.devnull, 'w')

            ## Open Status File

            statusFile = open(tempStatusPath, 'w')
            statusFile.writelines('Setting up paths,0')
            statusFile.close()

            finalPath = ''
            self.permPath = ''

            try:
                website = ChildDomains.objects.get(domain=domainName)
                externalApp = website.master.externalApp
                self.masterDomain = website.master.domain

                if home == '0':
                    path = self.extraArgs['path']
                    finalPath = website.path.rstrip('/') + "/" + path + "/"
                else:
                    finalPath = website.path

                if website.master.package.dataBases > website.master.databases_set.all().count():
                    pass
                else:
                    raise BaseException("Maximum database limit reached for this website.")

                statusFile = open(tempStatusPath, 'w')
                statusFile.writelines('Setting up Database,20')
                statusFile.close()

                dbName, dbUser, dbPassword = self.dbCreation(tempStatusPath, website.master)
                self.permPath = website.path

            except:
                website = Websites.objects.get(domain=domainName)
                externalApp = website.externalApp
                self.masterDomain = website.domain

                if home == '0':
                    path = self.extraArgs['path']
                    finalPath = "/home/" + domainName + "/public_html/" + path + "/"
                else:
                    finalPath = "/home/" + domainName + "/public_html/"

                if website.package.dataBases > website.databases_set.all().count():
                    pass
                else:
                    raise BaseException("Maximum database limit reached for this website.")

                statusFile = open(tempStatusPath, 'w')
                statusFile.writelines('Setting up Database,20')
                statusFile.close()

                dbName, dbUser, dbPassword = self.dbCreation(tempStatusPath, website)
                self.permPath = '/home/%s/public_html' % (website.domain)

            ## Security Check

            command = 'chmod 755 %s' % (self.permPath)
            ProcessUtilities.executioner(command)

            if finalPath.find("..") > -1:
                raise BaseException("Specified path must be inside virtual host home.")

            if not os.path.exists(finalPath):
                command = 'mkdir -p ' + finalPath
                ProcessUtilities.executioner(command, externalApp)

            ## checking for directories/files

            if self.dataLossCheck(finalPath, tempStatusPath) == 0:
                raise BaseException('Directory is not empty.')

            ####

            statusFile = open(tempStatusPath, 'w')
            statusFile.writelines('Downloading Mautic Core,30')
            statusFile.close()

            command = "wget https://github.com/mautic/mautic/releases/download/3.1.0/3.1.0.zip"
            ProcessUtilities.outputExecutioner(command, externalApp, None, finalPath)

            statusFile = open(tempStatusPath, 'w')
            statusFile.writelines('Extracting Mautic Core,50')
            statusFile.close()

            command = "unzip 3.1.0.zip"
            ProcessUtilities.outputExecutioner(command, externalApp, None, finalPath)

            ##

            statusFile = open(tempStatusPath, 'w')
            statusFile.writelines('Running Mautic installer,70')
            statusFile.close()

            if home == '0':
                path = self.extraArgs['path']
                finalURL = domainName + '/' + path
            else:
                finalURL = domainName

            localDB = "/home/cyberpanel/" + str(randint(1000, 9999))

            localDBContent = """<?php
// Example local.php to test install (to adapt of course)
$parameters = array(
	// Do not set db_driver and mailer_from_name as they are used to assume Mautic is installed
	'db_host' => 'localhost',
	'db_table_prefix' => null,
	'db_port' => 3306,
	'db_name' => '%s',
	'db_user' => '%s',
	'db_password' => '%s',
	'db_backup_tables' => true,
	'db_backup_prefix' => 'bak_',
	'admin_email' => '%s',
	'admin_password' => '%s',
	'mailer_transport' => null,
	'mailer_host' => null,
	'mailer_port' => null,
	'mailer_user' => null,
	'mailer_password' => null,
	'mailer_api_key' => null,
	'mailer_encryption' => null,
	'mailer_auth_mode' => null,
);""" % (dbName, dbUser, dbPassword, email, password)

            writeToFile = open(localDB, 'w')
            writeToFile.write(localDBContent)
            writeToFile.close()

            command = 'rm -rf %s/app/config/local.php' % (finalPath)
            ProcessUtilities.executioner(command)

            command = 'mv %s %s/app/config/local.php' % (localDB, finalPath)
            ProcessUtilities.executioner(command)

            command = "/usr/local/lsws/lsphp72/bin/php bin/console mautic:install http://%s" % (finalURL)
            result = ProcessUtilities.outputExecutioner(command, 'root', None, finalPath)

            if result.find('Install complete') == -1:
                raise BaseException(result)


            ##

            from filemanager.filemanager import FileManager

            fm = FileManager(None, None)
            fm.fixPermissions(self.masterDomain)

            installUtilities.reStartLiteSpeedSocket()

            statusFile = open(tempStatusPath, 'w')
            statusFile.writelines("Successfully Installed. [200]")
            statusFile.close()
            return 0


        except BaseException as msg:
            # remove the downloaded files
            FNULL = open(os.devnull, 'w')

            homeDir = "/home/" + domainName + "/public_html"

            if ProcessUtilities.decideDistro() == ProcessUtilities.centos or ProcessUtilities.decideDistro() == ProcessUtilities.cent8:
                groupName = 'nobody'
            else:
                groupName = 'nogroup'

            if not os.path.exists(homeDir):
                command = "chown " + externalApp + ":" + groupName + " " + homeDir
                ProcessUtilities.executioner(command, externalApp)

            try:
                mysqlUtilities.deleteDatabase(dbName, dbUser)
                db = Databases.objects.get(dbName=dbName)
                db.delete()
            except:
                pass

            command = 'chmod 750 %s' % (self.permPath)
            ProcessUtilities.executioner(command)


            statusFile = open(self.tempStatusPath, 'w')
            statusFile.writelines(str(msg) + " [404]")
            statusFile.close()
            return 0

    def updatePackage(self):
        try:

            package = self.extraArgs['package']

            from serverStatus.serverStatusUtil import ServerStatusUtil

            f = open(ServerStatusUtil.lswsInstallStatusPath, 'a')

            if ProcessUtilities.decideDistro() == ProcessUtilities.ubuntu or ProcessUtilities.decideDistro() == ProcessUtilities.ubuntu20:

                if package == 'all':
                    command = 'DEBIAN_FRONTEND=noninteractive apt-get update -y'
                    f.write(ProcessUtilities.outputExecutioner(command))

                    f.flush()

                    command = 'apt-get upgrade -y'
                    f.write(ProcessUtilities.outputExecutioner(command))
                else:
                    command = 'apt-get install --only-upgrade %s -y' % (package)
                    f.write(ProcessUtilities.outputExecutioner(command))

                f.close()
            elif ProcessUtilities.decideDistro() == ProcessUtilities.centos or ProcessUtilities.decideDistro() == ProcessUtilities.cent8:
                if package == 'all':
                    command = 'yum update -y'
                    f.write(ProcessUtilities.outputExecutioner(command))
                else:
                    command = 'yum update %s -y' % (package)
                    f.write(ProcessUtilities.outputExecutioner(command))

            f.close()

            logging.statusWriter(ServerStatusUtil.lswsInstallStatusPath,
                                                      'Package(s) upgraded successfully. [200]',
                                                      1)

        except BaseException as msg:
            from serverStatus.serverStatusUtil import ServerStatusUtil
            logging.statusWriter(ServerStatusUtil.lswsInstallStatusPath, 'Failed. Error: %s. [404]' % (str(msg)), 1)
            return 0

    def convertDomainToSite(self):
        try:

            from websiteFunctions.website import WebsiteManager
            import json, time

            request = self.extraArgs['request']

            ##

            statusFile = open(self.tempStatusPath, 'w')
            statusFile.writelines('Deleting domain as child..,20')
            statusFile.close()

            data = json.loads(request.body)

            if data['package'] == None or data['domainName'] == None or data['adminEmail'] == None \
                    or data['phpSelection'] == None or data['websiteOwner'] == None:
                raise BaseException('Please provide all values.')

            domainName = data['domainName']

            childDomain = ChildDomains.objects.get(domain=domainName)
            path = childDomain.path

            wm = WebsiteManager()

            wm.submitDomainDeletion(request.session['userID'], {'websiteName': domainName})
            time.sleep(5)

            ##

            statusFile = open(self.tempStatusPath, 'w')
            statusFile.writelines('Creating domain as website..,40')
            statusFile.close()

            resp = wm.submitWebsiteCreation(request.session['userID'], data)
            respData = json.loads(resp.content.decode('utf-8'))

            ##

            while True:
                respDataStatus = ProcessUtilities.outputExecutioner("cat " + respData['tempStatusPath'])

                if respDataStatus.find('[200]') > -1:
                    break
                elif respDataStatus.find('[404]') > -1:
                    statusFile = open(self.tempStatusPath, 'w')
                    statusFile.writelines(respDataStatus['currentStatus'] + '  [404]')
                    statusFile.close()
                    return 0
                else:
                    statusFile = open(self.tempStatusPath, 'w')
                    statusFile.writelines(respDataStatus)
                    statusFile.close()
                    time.sleep(1)

            statusFile = open(self.tempStatusPath, 'w')
            statusFile.writelines('Moving data..,80')
            statusFile.close()


            command = 'rm -rf  /home/%s/public_html' % (domainName)
            ProcessUtilities.executioner(command)

            command = 'mv %s /home/%s/public_html' % (path, domainName)
            ProcessUtilities.executioner(command)

            from filemanager.filemanager import FileManager

            fm = FileManager(None, None)
            fm.fixPermissions(domainName)

            statusFile = open(self.tempStatusPath, 'w')
            statusFile.writelines('Successfully converted. [200]')
            statusFile.close()

        except BaseException as msg:
            statusFile = open(self.tempStatusPath, 'w')
            statusFile.writelines(str(msg) + " [404]")
            statusFile.close()
            return 0

    def installWPCLI(self):
        try:
            command = 'wget https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar'
            ProcessUtilities.executioner(command)

            command = 'chmod +x wp-cli.phar'
            ProcessUtilities.executioner(command)

            command = 'mv wp-cli.phar /usr/bin/wp'
            ProcessUtilities.executioner(command)

        except BaseException as msg:
            logging.writeToFile(str(msg) + ' [ApplicationInstaller.installWPCLI]')

    def dataLossCheck(self, finalPath, tempStatusPath):
        dirFiles = os.listdir(finalPath)

        if len(dirFiles) <= 3:
            return 1
        else:
            return 0

    def installGit(self):
        try:
            if os.path.exists("/etc/lsb-release"):
                command = 'apt -y install git'
                ProcessUtilities.executioner(command)
            else:

                command = 'yum install git -y'
                ProcessUtilities.executioner(command)

        except BaseException as msg:
            logging.writeToFile(str(msg) + ' [ApplicationInstaller.installGit]')

    def dbCreation(self, tempStatusPath, website):
        passFile = "/etc/cyberpanel/mysqlPassword"

        try:
            import json
            jsonData = json.loads(open(passFile, 'r').read())

            mysqlhost = jsonData['mysqlhost']
            ApplicationInstaller.LOCALHOST = mysqlhost
        except:
            pass

        try:
            dbName = randomPassword.generate_pass()
            dbUser = dbName
            dbPassword = randomPassword.generate_pass()

            ## DB Creation

            if Databases.objects.filter(dbName=dbName).exists() or Databases.objects.filter(
                    dbUser=dbUser).exists():
                statusFile = open(tempStatusPath, 'w')
                statusFile.writelines(
                    "This database or user is already taken." + " [404]")
                statusFile.close()
                return 0

            result = mysqlUtilities.createDatabase(dbName, dbUser, dbPassword)

            if result == 1:
                pass
            else:
                statusFile = open(tempStatusPath, 'w')
                statusFile.writelines(
                    "Not able to create database." + " [404]")
                statusFile.close()
                return 0

            db = Databases(website=website, dbName=dbName, dbUser=dbUser)
            db.save()

            return dbName, dbUser, dbPassword

        except BaseException as msg:
            logging.writeToFile(str(msg) + '[ApplicationInstallerdbCreation]')

    def installWordPress(self):
        try:

            admin = self.extraArgs['admin']
            domainName = self.extraArgs['domainName']
            home = self.extraArgs['home']
            tempStatusPath = self.extraArgs['tempStatusPath']
            self.tempStatusPath = tempStatusPath
            blogTitle = self.extraArgs['blogTitle']
            adminUser = self.extraArgs['adminUser']
            adminPassword = self.extraArgs['adminPassword']
            adminEmail = self.extraArgs['adminEmail']

            FNULL = open(os.devnull, 'w')

            ### Check WP CLI

            try:
                command = 'wp --info'
                outout = ProcessUtilities.outputExecutioner(command)

                if not outout.find('WP-CLI root dir:') > -1:
                    self.installWPCLI()
            except subprocess.CalledProcessError:
                self.installWPCLI()

            ## Open Status File

            statusFile = open(tempStatusPath, 'w')
            statusFile.writelines('Setting up paths,0')
            statusFile.close()

            finalPath = ''
            self.permPath = ''

            try:
                website = ChildDomains.objects.get(domain=domainName)
                externalApp = website.master.externalApp
                self.masterDomain = website.master.domain

                if home == '0':
                    path = self.extraArgs['path']
                    finalPath = website.path.rstrip('/') + "/" + path + "/"
                else:
                    finalPath = website.path

                if website.master.package.dataBases > website.master.databases_set.all().count():
                    pass
                else:
                    raise BaseException("Maximum database limit reached for this website.")

                statusFile = open(tempStatusPath, 'w')
                statusFile.writelines('Setting up Database,20')
                statusFile.close()

                dbName, dbUser, dbPassword = self.dbCreation(tempStatusPath, website.master)
                self.permPath = website.path

            except:
                website = Websites.objects.get(domain=domainName)
                externalApp = website.externalApp
                self.masterDomain = website.domain

                if home == '0':
                    path = self.extraArgs['path']
                    finalPath = "/home/" + domainName + "/public_html/" + path + "/"
                else:
                    finalPath = "/home/" + domainName + "/public_html/"

                if website.package.dataBases > website.databases_set.all().count():
                    pass
                else:
                    raise BaseException("Maximum database limit reached for this website.")

                statusFile = open(tempStatusPath, 'w')
                statusFile.writelines('Setting up Database,20')
                statusFile.close()

                dbName, dbUser, dbPassword = self.dbCreation(tempStatusPath, website)
                self.permPath = '/home/%s/public_html' % (website.domain)

            ## Security Check

            command = 'chmod 755 %s' % (self.permPath)
            ProcessUtilities.executioner(command)

            if finalPath.find("..") > -1:
                raise BaseException("Specified path must be inside virtual host home.")

            if not os.path.exists(finalPath):
                command = 'mkdir -p ' + finalPath
                ProcessUtilities.executioner(command, externalApp)

            ## checking for directories/files

            if self.dataLossCheck(finalPath, tempStatusPath) == 0:
                raise BaseException('Directory is not empty.')

            ####

            statusFile = open(tempStatusPath, 'w')
            statusFile.writelines('Downloading WordPress Core,30')
            statusFile.close()

            command = "wp core download --allow-root --path=" + finalPath
            ProcessUtilities.executioner(command, externalApp)

            ##

            statusFile = open(tempStatusPath, 'w')
            statusFile.writelines('Configuring the installation,40')
            statusFile.close()

            command = "wp core config --dbname=" + dbName + " --dbuser=" + dbUser + " --dbpass=" + dbPassword + " --dbhost=%s --dbprefix=wp_ --allow-root --path=" % (ApplicationInstaller.LOCALHOST) + finalPath
            ProcessUtilities.executioner(command, externalApp)

            if home == '0':
                path = self.extraArgs['path']
                finalURL = domainName + '/' + path
            else:
                finalURL = domainName

            command = 'wp core install --url="http://' + finalURL + '" --title="' + blogTitle + '" --admin_user="' + adminUser + '" --admin_password="' + adminPassword + '" --admin_email="' + adminEmail + '" --allow-root --path=' + finalPath
            ProcessUtilities.executioner(command, externalApp)

            ##

            statusFile = open(tempStatusPath, 'w')
            statusFile.writelines('Installing LSCache Plugin,80')
            statusFile.close()

            command = "wp plugin install litespeed-cache --allow-root --path=" + finalPath
            ProcessUtilities.executioner(command, externalApp)

            statusFile = open(tempStatusPath, 'w')
            statusFile.writelines('Activating LSCache Plugin,90')
            statusFile.close()

            command = "wp plugin activate litespeed-cache --allow-root --path=" + finalPath
            ProcessUtilities.executioner(command, externalApp)

            ##

            from filemanager.filemanager import FileManager

            fm = FileManager(None, None)
            fm.fixPermissions(self.masterDomain)

            statusFile = open(tempStatusPath, 'w')
            statusFile.writelines("Successfully Installed. [200]")
            statusFile.close()
            return 0


        except BaseException as msg:
            # remove the downloaded files
            FNULL = open(os.devnull, 'w')

            homeDir = "/home/" + domainName + "/public_html"

            if ProcessUtilities.decideDistro() == ProcessUtilities.centos or ProcessUtilities.decideDistro() == ProcessUtilities.cent8:
                groupName = 'nobody'
            else:
                groupName = 'nogroup'

            if not os.path.exists(homeDir):
                command = "chown " + externalApp + ":" + groupName + " " + homeDir
                ProcessUtilities.executioner(command, externalApp)

            try:
                mysqlUtilities.deleteDatabase(dbName, dbUser)
                db = Databases.objects.get(dbName=dbName)
                db.delete()
            except:
                pass

            command = 'chmod 750 %s' % (self.permPath)
            ProcessUtilities.executioner(command)


            statusFile = open(self.tempStatusPath, 'w')
            statusFile.writelines(str(msg) + " [404]")
            statusFile.close()
            return 0

    def installPrestaShop(self):
        try:

            admin = self.extraArgs['admin']
            domainName = self.extraArgs['domainName']
            home = self.extraArgs['home']
            shopName = self.extraArgs['shopName']
            firstName = self.extraArgs['firstName']
            lastName = self.extraArgs['lastName']
            databasePrefix = self.extraArgs['databasePrefix']
            email = self.extraArgs['email']
            password = self.extraArgs['password']
            tempStatusPath = self.extraArgs['tempStatusPath']
            self.tempStatusPath = tempStatusPath

            FNULL = open(os.devnull, 'w')

            ## Open Status File

            statusFile = open(tempStatusPath, 'w')
            statusFile.writelines('Setting up paths,0')
            statusFile.close()

            finalPath = ''
            self.permPath = ''

            try:
                website = ChildDomains.objects.get(domain=domainName)
                externalApp = website.master.externalApp
                self.masterDomain = website.master.domain

                if home == '0':
                    path = self.extraArgs['path']
                    finalPath = website.path.rstrip('/') + "/" + path + "/"
                else:
                    finalPath = website.path + "/"

                if website.master.package.dataBases > website.master.databases_set.all().count():
                    pass
                else:
                    raise BaseException("Maximum database limit reached for this website.")

                statusFile = open(tempStatusPath, 'w')
                statusFile.writelines('Setting up Database,20')
                statusFile.close()

                dbName, dbUser, dbPassword = self.dbCreation(tempStatusPath, website.master)
                self.permPath = website.path

            except:
                website = Websites.objects.get(domain=domainName)
                externalApp = website.externalApp
                self.masterDomain = website.domain

                if home == '0':
                    path = self.extraArgs['path']
                    finalPath = "/home/" + domainName + "/public_html/" + path + "/"
                else:
                    finalPath = "/home/" + domainName + "/public_html/"

                if website.package.dataBases > website.databases_set.all().count():
                    pass
                else:
                    raise BaseException("Maximum database limit reached for this website.")

                statusFile = open(tempStatusPath, 'w')
                statusFile.writelines('Setting up Database,20')
                statusFile.close()

                dbName, dbUser, dbPassword = self.dbCreation(tempStatusPath, website)
                self.permPath = '/home/%s/public_html' % (website.domain)

            ## Security Check

            command = 'chmod 755 %s' % (self.permPath)
            ProcessUtilities.executioner(command)

            if finalPath.find("..") > -1:
                raise BaseException('Specified path must be inside virtual host home.')

            if not os.path.exists(finalPath):
                command = 'mkdir -p ' + finalPath
                ProcessUtilities.executioner(command, externalApp)

            ## checking for directories/files

            if self.dataLossCheck(finalPath, tempStatusPath) == 0:
                raise BaseException('Directory is not empty.')

            ####

            statusFile = open(tempStatusPath, 'w')
            statusFile.writelines('Downloading and extracting PrestaShop Core..,30')
            statusFile.close()

            command = "wget https://download.prestashop.com/download/releases/prestashop_1.7.4.2.zip -P %s" % (
                finalPath)
            ProcessUtilities.executioner(command, externalApp)

            command = "unzip -o %sprestashop_1.7.4.2.zip -d " % (finalPath) + finalPath
            ProcessUtilities.executioner(command, externalApp)

            command = "unzip -o %sprestashop.zip -d " % (finalPath) + finalPath
            ProcessUtilities.executioner(command, externalApp)

            ##

            statusFile = open(tempStatusPath, 'w')
            statusFile.writelines('Configuring the installation,40')
            statusFile.close()

            if home == '0':
                path = self.extraArgs['path']
                # finalURL = domainName + '/' + path
                finalURL = domainName
            else:
                finalURL = domainName

            statusFile = open(tempStatusPath, 'w')
            statusFile.writelines('Installing and configuring PrestaShop..,60')
            statusFile.close()

            command = "php " + finalPath + "install/index_cli.php --domain=" + finalURL + \
                      " --db_server=localhost --db_name=" + dbName + " --db_user=" + dbUser + " --db_password=" + dbPassword \
                      + " --name='" + shopName + "' --firstname=" + firstName + " --lastname=" + lastName + \
                      " --email=" + email + " --password=" + password
            ProcessUtilities.executioner(command, externalApp)

            ##

            command = "rm -rf " + finalPath + "install"
            ProcessUtilities.executioner(command, externalApp)

            ##

            from filemanager.filemanager import FileManager

            fm = FileManager(None, None)
            fm.fixPermissions(self.masterDomain)

            statusFile = open(tempStatusPath, 'w')
            statusFile.writelines("Successfully Installed. [200]")
            statusFile.close()
            return 0


        except BaseException as msg:
            # remove the downloaded files

            homeDir = "/home/" + domainName + "/public_html"

            if ProcessUtilities.decideDistro() == ProcessUtilities.centos or ProcessUtilities.decideDistro() == ProcessUtilities.cent8:
                groupName = 'nobody'
            else:
                groupName = 'nogroup'

            if not os.path.exists(homeDir):
                command = "chown -R " + externalApp + ":" + groupName + " " + homeDir
                ProcessUtilities.executioner(command, externalApp)

            try:
                mysqlUtilities.deleteDatabase(dbName, dbUser)
                db = Databases.objects.get(dbName=dbName)
                db.delete()
            except:
                pass

            command = 'chmod 750 %s' % (self.permPath)
            ProcessUtilities.executioner(command)

            statusFile = open(self.tempStatusPath, 'w')
            statusFile.writelines(str(msg) + " [404]")
            statusFile.close()
            return 0

    def installJoomla(self):

        try:

            domainName = self.extraArgs['domainName']
            finalPath = self.extraArgs['finalPath']
            virtualHostUser = self.extraArgs['virtualHostUser']
            dbName = self.extraArgs['dbName']
            dbUser = self.extraArgs['dbUser']
            dbPassword = self.extraArgs['dbPassword']
            username = self.extraArgs['username']
            password = self.extraArgs['password']
            prefix = self.extraArgs['prefix']
            sitename = self.extraArgs['sitename']
            tempStatusPath = self.extraArgs['tempStatusPath']
            self.tempStatusPath = tempStatusPath

            FNULL = open(os.devnull, 'w')

            permPath = '/home/%s/public_html' % (domainName)
            command = 'chmod 755 %s' % (permPath)
            ProcessUtilities.executioner(command)

            if not os.path.exists(finalPath):
                os.makedirs(finalPath)

            ## checking for directories/files

            if self.dataLossCheck(finalPath, tempStatusPath) == 0:
                raise BaseException('Directory is not empty.')

            ## Get Joomla

            os.chdir(finalPath)

            if not os.path.exists("staging.zip"):
                command = 'wget --no-check-certificate https://github.com/joomla/joomla-cms/archive/staging.zip -P ' + finalPath
                ProcessUtilities.executioner(command, virtualHostUser)
            else:
                raise BaseException('File already exists.')

            command = 'unzip ' + finalPath + 'staging.zip -d ' + finalPath
            ProcessUtilities.executioner(command, virtualHostUser)

            command = 'rm -f %s' % (finalPath + 'staging.zip')
            ProcessUtilities.executioner(command, virtualHostUser)

            command = 'cp -r ' + finalPath + 'joomla-cms-staging/. ' + finalPath
            ProcessUtilities.executioner(command, virtualHostUser)

            command = 'chown -R cyberpanel:cyberpanel %s' % (finalPath)
            ProcessUtilities.executioner(command)

            shutil.rmtree(finalPath + "joomla-cms-staging")
            os.rename(finalPath + "installation/configuration.php-dist", finalPath + "configuration.php")
            os.rename(finalPath + "robots.txt.dist", finalPath + "robots.txt")
            os.rename(finalPath + "htaccess.txt", finalPath + ".htaccess")

            ## edit config file

            statusFile = open(tempStatusPath, 'w')
            statusFile.writelines('Creating configuration files.,40')
            statusFile.close()

            configfile = finalPath + "configuration.php"

            data = open(configfile, "r").readlines()

            writeDataToFile = open(configfile, "w")

            secret = randomPassword.generate_pass()

            defDBName = "   public $user = '" + dbName + "';" + "\n"
            defDBUser = "   public $db = '" + dbUser + "';" + "\n"
            defDBPassword = "   public $password = '" + dbPassword + "';" + "\n"
            secretKey = "   public $secret = '" + secret + "';" + "\n"
            logPath = "   public $log_path = '" + finalPath + "administrator/logs';" + "\n"
            tmpPath = "   public $tmp_path = '" + finalPath + "administrator/tmp';" + "\n"
            dbprefix = "   public $dbprefix = '" + prefix + "';" + "\n"
            sitename = "   public $sitename = '" + sitename + "';" + "\n"

            for items in data:
                if items.find("public $user ") > -1:
                    writeDataToFile.writelines(defDBUser)
                elif items.find("public $password ") > -1:
                    writeDataToFile.writelines(defDBPassword)
                elif items.find("public $db ") > -1:
                    writeDataToFile.writelines(defDBName)
                elif items.find("public $log_path ") > -1:
                    writeDataToFile.writelines(logPath)
                elif items.find("public $tmp_path ") > -1:
                    writeDataToFile.writelines(tmpPath)
                elif items.find("public $secret ") > -1:
                    writeDataToFile.writelines(secretKey)
                elif items.find("public $dbprefix ") > -1:
                    writeDataToFile.writelines(dbprefix)
                elif items.find("public $sitename ") > -1:
                    writeDataToFile.writelines(sitename)
                elif items.find("/*") > -1:
                    pass
                elif items.find(" *") > -1:
                    pass
                else:
                    writeDataToFile.writelines(items)

            writeDataToFile.close()

            statusFile = open(tempStatusPath, 'w')
            statusFile.writelines('Creating default user..,70')
            statusFile.close()

            # Rename SQL db prefix

            f1 = open(finalPath + 'installation/sql/mysql/joomla.sql', 'r')
            f2 = open(finalPath + 'installation/sql/mysql/joomlaInstall.sql', 'w')
            for line in f1:
                f2.write(line.replace('#__', prefix))
            f1.close()
            f2.close()

            # Restore SQL
            proc = subprocess.Popen(["mysql", "--user=%s" % dbUser, "--password=%s" % dbPassword, dbName],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE)

            usercreation = """INSERT INTO `%susers`
            (`name`, `username`, `password`, `params`)
            VALUES ('Administrator', '%s',
            '%s', '');
            INSERT INTO `%suser_usergroup_map` (`user_id`,`group_id`)
            VALUES (LAST_INSERT_ID(),'8');""" % (prefix, username, password, prefix)

            out, err = proc.communicate(
                open(finalPath + 'installation/sql/mysql/joomlaInstall.sql', 'rb').read() + ("\n" + usercreation).encode('utf-8'))

            shutil.rmtree(finalPath + "installation")

            if ProcessUtilities.decideDistro() == ProcessUtilities.centos or ProcessUtilities.decideDistro() == ProcessUtilities.cent8:
                groupName = 'nobody'
            else:
                groupName = 'nogroup'

            command = "chown -R " + virtualHostUser + ":" + groupName + " " + finalPath
            ProcessUtilities.executioner(command)

            vhost.addRewriteRules(domainName)

            installUtilities.reStartLiteSpeedSocket()

            permPath = '/home/%s/public_html' % (domainName)
            command = 'chmod 750 %s' % (permPath)
            ProcessUtilities.executioner(command)

            statusFile = open(tempStatusPath, 'w')
            statusFile.writelines("Successfully Installed. [200]")
            statusFile.close()
            return 0

        except BaseException as msg:
            # remove the downloaded files

            homeDir = "/home/" + domainName + "/public_html"

            if ProcessUtilities.decideDistro() == ProcessUtilities.centos or ProcessUtilities.decideDistro() == ProcessUtilities.cent8:
                groupName = 'nobody'
            else:
                groupName = 'nogroup'

            if not os.path.exists(homeDir):
                command = "chown -R " + virtualHostUser + ":" + groupName + " " + homeDir
                ProcessUtilities.executioner(command)

            try:
                mysqlUtilities.deleteDatabase(dbName, dbUser)
                db = Databases.objects.get(dbName=dbName)
                db.delete()
            except:
                pass

            permPath = '/home/%s/public_html' % (domainName)
            command = 'chmod 750 %s' % (permPath)
            ProcessUtilities.executioner(command)

            statusFile = open(self.tempStatusPath, 'w')
            statusFile.writelines(str(msg) + " [404]")
            statusFile.close()
            logging.writeToFile(str(msg))
            return 0

    # def installMagento(self):
    #     try:
    #
    #         username = self.extraArgs['username']
    #         domainName = self.extraArgs['domainName']
    #         home = self.extraArgs['home']
    #         firstName = self.extraArgs['firstName']
    #         lastName = self.extraArgs['lastName']
    #         email = self.extraArgs['email']
    #         password = self.extraArgs['password']
    #         tempStatusPath = self.extraArgs['tempStatusPath']
    #         sampleData = self.extraArgs['sampleData']
    #         self.tempStatusPath = tempStatusPath
    #
    #         FNULL = open(os.devnull, 'w')
    #
    #         ## Open Status File
    #
    #         statusFile = open(tempStatusPath, 'w')
    #         statusFile.writelines('Setting up paths,0')
    #         statusFile.close()
    #
    #         finalPath = ''
    #         self.premPath = ''
    #
    #         try:
    #             website = ChildDomains.objects.get(domain=domainName)
    #             externalApp = website.master.externalApp
    #             self.masterDomain = website.master.domain
    #
    #             if home == '0':
    #                 path = self.extraArgs['path']
    #                 finalPath = website.path.rstrip('/') + "/" + path + "/"
    #             else:
    #                 finalPath = website.path + "/"
    #
    #             if website.master.package.dataBases > website.master.databases_set.all().count():
    #                 pass
    #             else:
    #                 raise BaseException( "Maximum database limit reached for this website.")
    #
    #             statusFile = open(tempStatusPath, 'w')
    #             statusFile.writelines('Setting up Database,20')
    #             statusFile.close()
    #
    #             dbName, dbUser, dbPassword = self.dbCreation(tempStatusPath, website.master)
    #             self.permPath = website.path
    #
    #         except:
    #             website = Websites.objects.get(domain=domainName)
    #             externalApp = website.externalApp
    #             self.masterDomain = website.domain
    #
    #             if home == '0':
    #                 path = self.extraArgs['path']
    #                 finalPath = "/home/" + domainName + "/public_html/" + path + "/"
    #             else:
    #                 finalPath = "/home/" + domainName + "/public_html/"
    #
    #             if website.package.dataBases > website.databases_set.all().count():
    #                 pass
    #             else:
    #                 raise BaseException( "Maximum database limit reached for this website.")
    #
    #             statusFile = open(tempStatusPath, 'w')
    #             statusFile.writelines('Setting up Database,20')
    #             statusFile.close()
    #
    #             dbName, dbUser, dbPassword = self.dbCreation(tempStatusPath, website)
    #             self.permPath = '/home/%s/public_html' % (website.domain)
    #
    #         ## Security Check
    #
    #         if finalPath.find("..") > -1:
    #             raise BaseException( "Specified path must be inside virtual host home.")
    #
    #         command = 'chmod 755 %s' % (self.permPath)
    #         ProcessUtilities.executioner(command)
    #
    #         if not os.path.exists(finalPath):
    #             command = 'mkdir -p ' + finalPath
    #             ProcessUtilities.executioner(command, externalApp)
    #
    #         ## checking for directories/files
    #
    #         if self.dataLossCheck(finalPath, tempStatusPath) == 0:
    #             raise BaseException('Directory not empty.')
    #
    #         ####
    #
    #         statusFile = open(tempStatusPath, 'w')
    #         statusFile.writelines('Downloading Magento Community Core via composer to document root ..,30')
    #         statusFile.close()
    #
    #         command = 'composer create-project --repository-url=https://repo.magento.com/ magento/project-community-edition %s' % (finalPath)
    #
    #         ProcessUtilities.executioner(command, externalApp)
    #
    #         ###
    #
    #         statusFile = open(tempStatusPath, 'w')
    #         statusFile.writelines('Configuring the installation,40')
    #         statusFile.close()
    #
    #         if home == '0':
    #             path = self.extraArgs['path']
    #             # finalURL = domainName + '/' + path
    #             finalURL = domainName
    #         else:
    #             finalURL = domainName
    #
    #         statusFile = open(tempStatusPath, 'w')
    #         statusFile.writelines('Installing and configuring Magento..,60')
    #         statusFile.close()
    #
    #         command = '/usr/local/lsws/lsphp73/bin/php -d memory_limit=512M %sbin/magento setup:install --base-url="http://%s" ' \
    #                   ' --db-host="localhost" --db-name="%s" --db-user="%s" --db-password="%s" --admin-firstname="%s" ' \
    #                   ' --admin-lastname="%s" --admin-email="%s" --admin-user="%s" --admin-password="%s" --language="%s" --timezone="%s" ' \
    #                   ' --use-rewrites=1 --search-engine="elasticsearch7" --elasticsearch-host="localhost" --elasticsearch-port="9200" ' \
    #                   ' --elasticsearch-index-prefix="%s"' \
    #                   % (finalPath, finalURL, dbName, dbUser, dbPassword, firstName, lastName, email, username, password, 'language', 'timezone', dbName )
    #
    #         result = ProcessUtilities.outputExecutioner(command, externalApp)
    #         logging.writeToFile(result)
    #
    #         ##
    #
    #         ProcessUtilities.executioner(command, externalApp)
    #
    #         ##
    #
    #         from filemanager.filemanager import FileManager
    #
    #         fm = FileManager(None, None)
    #         fm.fixPermissions(self.masterDomain)
    #
    #         installUtilities.reStartLiteSpeed()
    #
    #         statusFile = open(tempStatusPath, 'w')
    #         statusFile.writelines("Successfully Installed. [200]")
    #         statusFile.close()
    #         return 0
    #
    #
    #     except BaseException as msg:
    #         # remove the downloaded files
    #
    #         homeDir = "/home/" + domainName + "/public_html"
    #
    #         if ProcessUtilities.decideDistro() == ProcessUtilities.centos or ProcessUtilities.decideDistro() == ProcessUtilities.cent8:
    #             groupName = 'nobody'
    #         else:
    #             groupName = 'nogroup'
    #
    #         if not os.path.exists(homeDir):
    #             command = "chown -R " + externalApp + ":" + groupName + " " + homeDir
    #             ProcessUtilities.executioner(command, externalApp)
    #
    #         try:
    #             mysqlUtilities.deleteDatabase(dbName, dbUser)
    #             db = Databases.objects.get(dbName=dbName)
    #             db.delete()
    #         except:
    #             pass
    #
    #         permPath = '/home/%s/public_html' % (domainName)
    #         command = 'chmod 750 %s' % (permPath)
    #         ProcessUtilities.executioner(command)
    #
    #         statusFile = open(self.tempStatusPath, 'w')
    #         statusFile.writelines(str(msg) + " [404]")
    #         statusFile.close()
    #         return 0
