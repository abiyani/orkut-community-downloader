orkut-community-downloader
==========================

Download all the forum &amp; poll threads from an orkut community (by recursively navigating and saving pages using browser's "Save as" option). NO manual intervention required.

**Reason:**

Orkut is shutting down on September 30 2014 (http://en.blog.orkut.com/2014/06/tchau-orkut.html). Unfortunately there is no easy way (or at least we couldn't find any) to download all the forum posts &amp; polls of non-public communities ("Google Takeout", the official recommended way, downloads *only* the forum threads *you* started). Also, using something like `wget --recursive` is not an option, because orkut uses a lot of client side magic to render the page, hence the vanilla output of `GET <some_orkut_url>` is not useful.

**How it works:**

Since any modern browser renders the orkut webpage correctly, and also allows you to save the post-rendered version, you might try something like this yourself: Open a thread in the community, Ctrl+S, recurse! Well, this script automates this process (plus a few post-processing niceties at the end):

1. Figure out links to all forum &amp; poll threads in the community.

2. Open each thread in your browser, save it. If a thread is multi-page, then save each page by going through the "next" link chain.

3. Replace links in the html file to point to the local copy (wherever applicable). This makes browsing locally much more user friendly.
4. Optionally (with `--symlink-common-files` flag), it removes excessive duplication of various files across the `*_files` directories, by symlinking all the duplicate version to a single copy.

**How to use:**

*Note:* You will need `xdotool` to be installed (Ubuntu: `sudo apt-get install xdotool`). See https://github.com/abiyani/automate-save-page-as for details.

```
$ git clone --recursive https://github.com/abiyani/orkut-community-downloader.git  # Don't forget the --recursive flag!
$ cd orkut-community-downloader
$ ./orkut-community-downloader.py --community-id 125 --dest_dir ./mathematics_orkut_community
```

Feel free to email [@abiyani](https://github.com/abiyani) if you have any questions regarding the usage, and open issues if you notice any bug. I tested this script (by downloading a few communities I cared about) on Ubuntu 12.04 (Python 2.7.3, Google-Chrome 36).
