#!/usr/bin/python3
# vim: noai:ts=4:sw=4

# This software is licensed to you under the GNU General Public License,
# version 3 (GPLv3). There is NO WARRANTY for this software, express or
# implied, including the implied warranties of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. You should have received a copy of GPLv3
# along with this software; if not, see
# http://www.gnu.org/licenses/gpl-3.0.txt.
#
# Red Hat trademarks are not licensed under GPLv3. No permission is
# granted to use or replicate Red Hat trademarks that are incorporated
# in this software or its documentation.

from __future__ import print_function

import argparse
import difflib
import os
import re
import rpm
import signal
import subprocess

SELINUX = ''

def get_list_of_config(package):
    """ return list of config files for give package """
    result = subprocess.check_output(["/usr/bin/rpm", '-qc', package['name']], universal_newlines=True)
    # if package contains no files rpm will print localized "(contains no files)"
    if re.match( r'^(.*)$', result):
        result = []
    else:
        result = result.rstrip().split('\n')
    return result

def differ(file_name1, file_name2):
    """ returns True if files differ """
    try:
        subprocess.check_call(['/usr/bin/diff', '-q'])
        return False
    except CalledProcessError:
        return True

def remove(conf_file):
    if args.debug:
        print("rm {}".format(conf_file))
    else:
        os.unlink(conf_file)

def merge_conf_files(conf_file, other_file):
    # vimdiff, gvimdiff, meld return 0 even if file was not saved
    # we may handle it some way. check last modification? ask user?
    if arg.frontend == 'vimdiff':
        subprocess.check_call(['/usr/bin/vimdiff', conf_file, other_file])
        os.remove(other_file)
    elif arg.frontend == 'gvimdiff':
        subprocess.check_call(['/usr/bin/gvimdiff', conf_file, other_file])
        os.remove(other_file)
    elif arg.frontend == 'diffuse':
        subprocess.check_call(['/usr/bin/diffuse', conf_file, other_file])
        os.remove(other_file)
    elif arg.frontend == 'kdiff3':
        subprocess.check_call(['/usr/bin/kdiff3', conf_file, other_file, '-o', conf_file])
        os.remove(other_file)
        os.remove(conf_file+".orig")
    elif arg.frontend == 'meld':
        subprocess.check_call(['/usr/bin/meld', conf_file, other_file])
        os.remove(other_file)
    else:
        sys.stderr.write("Error: you did not selected any frontend for merge.")
        sys.exit(2)

def handle_rpmnew(conf_file, other_file):
    if not differ(conf_file, other_file):
        os.remove(other_file)
        return

    prompt = """ ==> Package distributor has shipped an updated version.
   What would you like to do about it ?  Your options are:
    Y or I  : install the package maintainer's version
    N or O  : keep your currently-installed version
      D     : show the differences between the versions
      M     : merge configuration files
      Z     : background this process to examine the situation
      S     : skip this file
 The default action is to keep your current version.
*** aliases (Y/I/N/O/D/Z/S) [default=N] ? """

    option = ""
    while (option not in ["Y", "I", "N", "O", "M", "S"]):
        print("Configuration file '{}'".format(conf_file))
        if SELINUX:
            print(subprocess.check_output(['/usr/bin/ls', '-ltrd', SELINUX, conf_file, other_file]))
        else:
            print(subprocess.check_output(['/usr/bin/ls', '-ltrd', conf_file, other_file]))
        print(prompt)
        try:
            option = raw_input("Your choice: ")
        except EOFError:
            option = "S"
        if not option:
            option = "N"
        option = option.upper()

        if option == "D":
            p1 = Popen(['/usr/bin/diff', '-u', conf_file, other_file], stdout=PIPE)
            p2 = Popen(["/usr/bin/less"], stdin=p1.stdout, stdout=PIPE)
            p1.stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
            output = p2.communicate()[0]
        if option == "Z":
            print("Run command 'fg' to continue")
            os.kill(os.getpid(), signal.SIGSTOP)
    if option in ["N", "O"]:
        os.remove(other_file)
    if option in ["Y", "I"]:
        shutil.copy2(other_file, conf_file)
        os.remove(other_file)
    if option == "M":
        merge_conf_files(conf_file, other_file)


def handle_rpmsave(conf_file, other_file):
    raise

def handle_package(package):
    """ does the main work for each package
        package is rpmHdr object
    """
    for conf_file in get_list_of_config(package):
        if os.access(conf_file + ".rpmnew", os.F_OK):
            handle_rpmnew(conf_file, conf_file + ".rpmsave")
        if os.access(conf_file + ".rpmsave", os.F_OK):
            handle_rpmsave(conf_file, conf_file + ".rpmsave")
        if os.access(conf_file + ".rpmorig", os.F_OK):
            handle_rpmsave(conf_file, conf_file + ".rpmorig")

parser = argparse.ArgumentParser()
parser.add_argument('-a', '--all', dest='all', action='store_true',
                   help='Check configuration files of all packages.')
parser.add_argument('-o', '--owner', dest='owner', action='append', metavar='PACKAGE',
                   help='Check only configuration files of given package.')
parser.add_argument('-f', '--frontend', dest='frontend', action='store', metavar='EDITOR',
                   help='Define which frontend should be used for merging. For list of valid types see man page.')
parser.add_argument('-c', '--clean', dest='clean', action='store_true',
                   help='Find and delete orphaned .rpmnew and .rpmsave files.')
parser.add_argument('-d', '--debug', dest='debug', action='store_true',
                   help='Dry run. Just show which file will be deleted.')
parser.add_argumetn('-D', '--diff', dest='diff', action='store_true',
                   help='Non-interactive diff mode. Useful to audit configs. Use with -a or -o options.'
parser.add_argument('-V', '--version', dest='version', action='store_true',
                   help='Display rpmconf version.')
parser.add_argument('-Z', dest='selinux', action='store_true',
                   help='Display SELinux context of old and new file.')

args = parser.parse_args()

if args.version:
    print(subprocess.check_output(["/usr/bin/rpm", '-q', 'rpmconf']))

print(args.owner)

packages = []
ts = rpm.TransactionSet()
if args.all:
    packages = [ ts.dbMatch() ]
elif args.owner:
    for o in args.owner:
        print(o)
        mi = ts.dbMatch('name', o)
        packages.append(mi)

for mi in packages:
    for package_hdr in mi:
        handle_package(package_hdr)
