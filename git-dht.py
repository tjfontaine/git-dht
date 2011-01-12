#!/usr/bin/env python

"""
Copyright (c) 2011 Timothy J Fontaine <tjfontaine@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import hashlib
import os
import sys

from ConfigParser import RawConfigParser
from fnmatch import fnmatch
from optparse import OptionParser
from socket import getaddrinfo

from dulwich.repo import Repo

from entangled.node import EntangledNode
from entangled.kademlia import contact

import twisted.internet.reactor

GIT_DHT_PORT = 39148

class FakeRead(object):
  def __init__(self, fp):
    self.fp = fp
    self.name = fp.name
  def readline(self):
    r = self.fp.readline()
    rs = r.lstrip()
    if rs:
      return rs
    else:
      return r
  def write(self, r):
    return self.fp.write(r)
  def close(self):
    return self.fp.close()

class GitDht(EntangledNode):
  def __init__(self, repos, *args, **kwargs):
    super(GitDht, self).__init__(*args, **kwargs)
    self.repos = repos

    for repo_name, rdict in self.repos.items():
      repo = rdict['repo']
      for ref in rdict['selected_refs']:
        head = repo.ref(ref)
        key = '%s:%s' % (repo_name, ref.replace('/', ':'))
        self.publishData('%s:head' % key, head)
        seen = []
        tosee = [sha for sha in repo[repo.ref(ref)].parents if sha not in seen]
        while len(tosee) > 0:
          sha = tosee.pop()
          if sha in seen:
            continue
          else:
            seen.append(sha)
          for s in repo[sha].parents:
            if s not in seen:
              tosee.append(s)
          k = '%s:%s' % (key, sha)
          self.publishData(k, head)
      self.publishData(repo_name, ','.join(rdict['selected_refs']))

  def searchForValue(self, key):
    h = hashlib.sha1()
    h.update(key)
    return self.iterativeFindValue(h.digest())
       

if __name__ == '__main__':
  gitconfig_default = {
      'config': os.path.join(os.environ['HOME'], '.git-dht'),
  }

  gitdht_config_default = {
      'port': GIT_DHT_PORT,
      'branches': 'master',
  }

  gitconfig_path = os.path.join(os.environ['HOME'], '.gitconfig')
  gitconfig_fr = FakeRead(open(gitconfig_path))
  gitconfig = RawConfigParser(gitconfig_default)
  gitconfig.readfp(gitconfig_fr)
  gitconfig_fr.close()

  if not gitconfig.has_section('dht'):
    gitconfig.add_section('dht')

  gitdht_config_path = gitconfig.get('dht', 'config')
  gitdht_config_fr = FakeRead(open(gitdht_config_path))
  gitdht_config = RawConfigParser(gitdht_config_default)
  gitdht_config.readfp(gitdht_config_fr)
  gitdht_config_fr.close()

  repos = {}

  gitdht_port = gitdht_config.getint('global', 'port')

  for section in gitdht_config.sections():
    if section != 'global':
      repo_path = gitdht_config.get(section, 'path')
      if os.path.exists(repo_path):
        repo = Repo(repo_path)
        branches = [r for r in repo.get_refs() if r.startswith('refs/heads/')]
        desired_branches = gitdht_config.get(section, 'branches').split(',')
        desired_branches = [b.strip() for b in desired_branches]
        selected_refs = []
        for b in branches:
          for d in desired_branches:
            refless = b.replace('refs/heads/', '')
            if fnmatch(b, d) or fnmatch(refless, d):
              print "Adding %s:%s @ %s" % (section, b, repo.ref(b))
              selected_refs.append(b)
        repos[section] = {
          'repo': repo,
          'selected_refs': selected_refs,
        }
        
      else:
        print "Repo %s doesn't exist at %s" % (section, repo_path)

  bootstrap_ips = getaddrinfo('bootstrap.git-dht.com', None, 0, 0, 0)
  bootstrap_ips = [(ip[4][0], GIT_DHT_PORT) for ip in bootstrap_ips] 

  gitdht = GitDht(repos, udpPort=gitdht_port)
  gitdht.joinNetwork(bootstrap_ips)

  from twisted.internet import task

  opts = OptionParser()
  opts.add_option('--search', action="store", dest="search_term",
    default=None, help="Periodically search for this term")
  opts.add_option('--search-timer', action="store", type="float", dest="search_timer",
    default=0, help="The timer for how often to search <= 0 is never")
  opts.add_option('--print-contacts', action="store_true", dest="print_contacts",
    default=False, help="Periodically print contacts")

  (options, arguments) = opts.parse_args()

  def searchResults(ret):
    if isinstance(ret, list):
      print 'Not found, received peers'
    else:
      print ret

  def searchNodes():
    print 'Searching ...'
    df = gitdht.searchForValue(options.search_term)
    df.addCallback(searchResults)
    gitdht.printContacts()

  if options.search_timer > 0:
    s = task.LoopingCall(searchNodes)
    s.start(options.search_timer)

  if options.print_contacts:
    t = task.LoopingCall(gitdht.printContacts)
    t.start(30)

  twisted.internet.reactor.run()
