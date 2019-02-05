# General

site_mapper is a utility that crawls a site and prints all the URLs starting from the one given as its arguments.
It limits its rate of calls according to the settings suggested in the site's robots.txt.

To run:
```bash
python3 site_mapper.py [ -o FILE ] SITE
# Example:
python3 site_mapper.py https://docs.aiohttp.org
```

# Requirements
* Python 3.7
* The packages listed in requirements.txt. To install them automatically run:
```bash
pip3 -r requirements.txt
```

