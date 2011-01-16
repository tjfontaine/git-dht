var path = require('path');
require.paths.push(path.join(process.env.HOME, path.join('lib', 'node')))

var DHT = require('dht');
var dns = require('dns');
var Repo = require('libgit2').Repo;
var RevWalk = require('libgit2').RevWalk;
var ini = require('iniparser');

var GIT_DHT_PORT = 39418;

var dhtconfig_path = path.join(process.env.HOME, '.git-dht');

var gitconfig = ini.parseSync(path.join(process.env.HOME, '.gitconfig'));

if (gitconfig.dht && gitconfig.dht.config) {
  dhtconfig_path = gitconfig.dht.config;
}

var dhtconfig = ini.parseSync(dhtconfig_path);

var dhtport = GIT_DHT_PORT;
var dhtid = undefined;

if (dhtconfig.global) {
  if (dhtconfig.global.port) {
    dhtport = parseInt(dhtconfig.global.port);
  }

  if (dhtconfig.global.id) {
    dhtid = dhtconfig.global.id;
  }
}

var dht = new DHT.DHT(dhtport);

/*
TODO XXX FIXME node-dht isn't prepared for this yet
if (dhtid) {
  dht.id = dht.id
}
*/

dht.start();

dns.resolveSrv('_bootstrap._udp.git-dht.com', function(err, recs) {
  addrs = []
  recs.forEach(function(r) {
    dns.lookup(r.name, function(lookup_err, address, family) {
      if(address) {
        var n = {
          address: address,
          port: r.port,
        }
        dht.bootstrap([n])
      }
    });
  });
});

repos = [];

for (section in dhtconfig) {
  if (section != 'global') {
    var repo_name = section;
    var repo_path = dhtconfig[section].path;
    var branch_matches = dhtconfig[section].branches.split(',');
    var repo = new Repo(repo_path);
    repo.refs(function(ref, head) {
      console.log('ref: ' + ref + ' head: ' + head)
      var head_commit = repo.lookup(head)
      var revwalk = new RevWalk(repo)
      revwalk.push(head_commit)
      var commit = revwalk.next()
      while(commit) {
        console.log(commit.id().toString())
        commit = revwalk.next()
      }
    });
    repos.push(repo);
    //repo.close()
  }
}

setTimeout(20000, function () { })
