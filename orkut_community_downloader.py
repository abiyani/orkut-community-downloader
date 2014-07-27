#!/usr/bin/env python

from optparse import OptionParser
import os
import shutil
from os.path import join as pjoin
import sys
import re
import hashlib
import collections
import tempfile
import subprocess


def read_file(f):
    return open(f, 'r').read()

next_link_log_file = None
prev_link_log_file = None
ORKUT_MAIN_URL = 'http://www.orkut.com/Main'


class LogFileCached():
    # Line format: <url> <file_path>
    def __init__(self, path):
        self.fd = open(path, 'a+')
        self.delimiter = "\t"
        lines = self.fd.readlines()
        self.data = {}
        for l in lines:
            s = l.strip().split(self.delimiter)
            assert len(s) == 2
            self.data[s[0]] = s[1]

    def add_line(self, url, file_path):
        assert url not in self
        self.fd.write("{}{}{}\n".format(url, self.delimiter, file_path))
        self.data[url] = file_path

    def __contains__(self, url):
        return url in self.data

    def __getitem__(self, url):
        return self.data[url]

    def __iter__(self):
        for k in self.data:
            yield k


def ensure_directory(d):
    if not os.path.isdir(d):
        os.makedirs(d)


def get_all_files_in_dir(d, suffix=""):
    return set([f for f in os.listdir(d) if os.path.isfile(pjoin(d, f)) and f.endswith(suffix)])


def dl(url, directory, suffix):
    subprocess.check_call(["./automate-save-page-as/save_page_as", url, "--destination", directory, "--suffix", suffix, "--load-wait-time", "8", "--save-wait-time", "8"])


def recursive_download(url, directory, cmm):
    ensure_directory(directory)
    next_pattern = re.compile('<a href="({}#Comm\w+\?+cmm={}[^"]+)"[^>]* class="MRC">next[^<]*</a>'.format(ORKUT_MAIN_URL, cmm))
    prev_pattern = re.compile('<a href="({}#Comm\w+\?+cmm={}[^"]+)"[^>]* class="MRC">[^ >]+ previous</a>'.format(ORKUT_MAIN_URL, cmm))
    counter = 0
    newfile = None
    while True:
        append_str = "-" + str(counter).zfill(4)
        prev_fileset = get_all_files_in_dir(directory, ".html")
        prevfile = newfile
        if url not in next_link_log_file:
            sys.stdout.write("\t\t- Downloading from url '{}' ...".format(url))
            dl(url, directory, append_str)
            curr_fileset = get_all_files_in_dir(directory, ".html")
            diff = curr_fileset - prev_fileset
            assert len(diff) == 1, "A download operation should increase number of file by exactly 1"
            newfile_temp = pjoin(directory, diff.pop())
            if re.compile('.*/-\d+\.html$').search(newfile_temp) is not None:
                sys.stdout.write("\t\tWARNING: The file was saved with incorrect name ('{}'). Will remove and redownload.\n".format(newfile_temp))
                dir_to_del = pjoin(directory, os.path.basename(str(newfile_temp).replace(".html", "_files")))
                assert os.path.isdir(dir_to_del)
                shutil.rmtree(dir_to_del)
                os.remove(newfile_temp)
                continue
            newfile = newfile_temp
            next_link_log_file.add_line(url, newfile)
            sys.stdout.write(" done ('{}')\n".format(newfile))
        else:
            newfile = next_link_log_file[url]
            sys.stdout.write("\t\t- Skipping URL '{}' (already downloaded at '{}'\n".format(url, newfile))

        data = read_file(newfile)

        # keep track of the "previous" link value so that we can replace url with local file path later
        mprev = prev_pattern.search(data)
        if mprev is not None and mprev.groups()[0] not in prev_link_log_file:
            prev_link_log_file.add_line(mprev.groups()[0], prevfile)

        mnext = next_pattern.search(data)
        if mnext is None:
            break
        url = mnext.groups()[0]

        counter += 1


# Make directory name safe for windows
def cleanup_dir_name(dname):
    unsafe_chars = '<>:"\\/|?*'
    safe_dname = ''.join([c for c in dname.strip() if c not in unsafe_chars])
    return ' '.join(safe_dname.split())  # Replace multiple spaces by single space, and remove trailing space


def replace_url_with_local_paths(start_directory):
    sys.stderr.write("INFO: Starting to fix links within '{}' directory tree\n".format(start_directory))
    for root, dirs, files in os.walk(start_directory):
        if root.endswith("_files"):
            continue
        for f in [t for t in files if t.endswith(".html")]:
            full_f = os.path.join(root, f)
            sys.stderr.write("\t- Processing file '{}' ...".format(full_f))
            contents = read_file(full_f)
            for k in next_link_log_file:
                contents = contents.replace('href="' + k + '"', 'href="' + os.path.relpath(next_link_log_file[k], root) + '"')
            for k in prev_link_log_file:
                contents = contents.replace('href="' + k + '"', 'href="' + os.path.relpath(prev_link_log_file[k], root) + '"')
            with open(full_f, "w") as fp:
                fp.write(contents)
            sys.stderr.write(" Done\n")


def symlink_common_files(bdir):
    if os.name != "posix":
        sys.stderr.write("WARNING: non-posix platform ... skipping symlink step\n")
        return
    sys.stderr.write("INFO: Beginning to symlink duplicate files ...")
    fileMD5 = lambda f: hashlib.md5(open(f).read()).hexdigest()  # Return MD5 of file as hex string
    md5_to_files = collections.defaultdict(list)
    for root, dirs, files in os.walk(bdir):
        if not root.endswith("_files"):
            continue
        for f in files:
            full_path = pjoin(root, f)
            if os.path.islink(full_path):
                continue
            md5_to_files[fileMD5(full_path)].append(full_path)

    common_files_dir = pjoin(bdir, "common_file_dir")
    ensure_directory(common_files_dir)
    for uniq_hash, files in md5_to_files.items():
        if len(md5_to_files[uniq_hash]) == 1:
            continue
        common_file_name = pjoin(common_files_dir, os.path.basename(files[0]))
        if os.path.isfile(common_file_name):
            # If the file with same name already exists, generate a random (but unique) name
            handle, commmon_file_name = tempfile.mkstemp(dir=common_files_dir)
            os.close(handle)

        shutil.copyfile(files[0], common_file_name)
        for f in files:
            sys.stderr.write("\t - Removing file '{}' (will symlink to: '{}'\n".format(f, common_file_name))
            os.remove(f)
            os.symlink(os.path.relpath(common_file_name, os.path.dirname(f)), f)


# Returns a tuple of (community_id, destination_directory, symlink)
def parse_and_validate_args():
    parser = OptionParser()
    parser.add_option("-i", "--community-id", dest="cmm", type="int",
                      help="ID of the community, e.g., If URL of the community homepage is http://www.orkut.com/Main#Community?cmm=125, then community-id is '125'")
    parser.add_option("-d", "--dest-dir", dest="dest_dir", type="string",
                      help="Will store all files inside this directory"),
    parser.add_option("-s", "--symlink-common-files", dest="symlink", action="store_true", default=False,
                      help="If provided, all common files across all '*_files' directories will be copied to a common directory, and " +
                           "all version will be replaced with a symlink to this location. Useful for saving space.")

    (options, args) = parser.parse_args()

    if not hasattr(options, "cmm") or not isinstance(options.cmm, (int, long)):
        sys.stderr.write("ERROR: --community-id must be provided and should be an integer\n")
        sys.exit(1)

    if not hasattr(options, "dest_dir") or not isinstance(options.dest_dir, (basestring)):
        sys.stderr.write("ERROR: --dest-dir must be provided.\n")
        sys.exit(1)

    # Create the directory if absent
    ensure_directory(options.dest_dir)

    return (options.cmm, options.dest_dir, options.symlink)


def main():
    global next_link_log_file, prev_link_log_file

    (cmm, bdir, to_symlink) = parse_and_validate_args()
    bdir = os.path.abspath(bdir)
    next_link_log_file = LogFileCached(pjoin(bdir, "next_link_log_file.txt"))
    prev_link_log_file = LogFileCached(pjoin(bdir, "prev_link_log_file.txt"))

    # Download all listings first
    LISTING_DIR = pjoin(bdir, "all_listings")
    sys.stderr.write("INFO: Downloading all listing files @ '{}'\n".format(LISTING_DIR))
    recursive_download(ORKUT_MAIN_URL + "#CommTopics?cmm={}".format(cmm), LISTING_DIR, cmm)  # Download all forum listings
    recursive_download(ORKUT_MAIN_URL + "#CommPolls?cmm={}".format(cmm), LISTING_DIR, cmm)  # Download all poll listings

    FORUM_DIR = pjoin(bdir, "forum")
    POLL_DIR = pjoin(bdir, "polls")

    all_files_concatenated = "\n\n".join([read_file(pjoin(LISTING_DIR, f)) for f in get_all_files_in_dir(LISTING_DIR, ".html")])

    generic_pattern = '<a class="AFB" href="({url_prefix}#Comm{{category}}\?cmm={cmm_id}&(tid=\d+|pid=\d+&pct=\d+))"[^>]*>([^<]*)</a>'.format(url_prefix=ORKUT_MAIN_URL, cmm_id=cmm)
    for category, directory in {"Msgs": FORUM_DIR, "Poll": POLL_DIR}.iteritems():
        all_pages_to_download = {group0: group3 for (group0, group1, group3) in
                                 re.compile(generic_pattern.format(category=category)).findall(all_files_concatenated)}
        counter = 1
        sys.stderr.write("INFO: Beginning to download for category '{}'. Will save @ '{}'\n".format(category, directory))
        for url, title in all_pages_to_download.iteritems():
            sys.stderr.write("\t- Downloading [{}: {} of {}]\n".format(category, counter, len(all_pages_to_download)))
            recursive_download(url, pjoin(directory, cleanup_dir_name(title)), cmm)
            counter += 1

    # Post-processing step (optional)
    replace_url_with_local_paths(bdir)

    if to_symlink:
        symlink_common_files(bdir)

main()
