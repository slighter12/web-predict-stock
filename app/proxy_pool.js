const request = require('request');
const cheerio = require('cheerio');
const sqlite3 = require('sqlite3');

const useragent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36';
class Options {
    constructor(uri, method, data) {
        this.uri = uri;
        this.method = method;
        this.headers = {
            'User-Agent': useragent,
        };
        if (data) {
            this.data = data;
        }
    }
}
// add Proxy.db info
const db = new sqlite3.Database('Proxy.db', err => {
    if (err) throw err;
    console.log('connect successful!');
});
db.run('CREATE TABLE IF NOT EXISTS proxy(ip char(15), port char(5), type char(10))');
const insertDb = (ip, port, type) => {
    db.run("INSERT INTO proxy VALUES(?, ?, ?)",[ip,port,type]);
};
// proxy website
const ipUrl = resolve =>{
    //this uri will ban my ip, need fix
    //let options = new Options('http://free-proxy.cz/zh/proxylist/country/TW/all/ping/level1', 'POST',
    //    {country: 'TW', protocol: 'all', anonymity: 'level1', send: '过滤器的代理服务器'});
    let options = new Options('http://www.aliveproxy.com/proxy-list/proxies.aspx/Taiwan-tw', 'GET');
    //console.log(options);
    requestProxy(options);
};
//access proxy data from website
const loadHtml = data =>{
    let $ = cheerio.load(data);
    let pattern = /\d*?\.\d*?\.\d*?\.\d*?:\d*?.*?((High anonymity)|(Anonymous))/g;
    let patternIP = /(\d{1,3})\.(\d{1,3}\.\d{1,3}\.\d{1,3}):(\d*?)-/;
    let list = $('tr.cw-list').get().map( repo =>{
        let $repo = $(repo);
        let content = $repo.text();
        if (content.match(pattern)) {
            let word = content.match(patternIP);
            let IP = `${word[1]}.${word[2]}`;
            let PORT = word[3].replace(new RegExp(word[1]),'');
            // console.log(`IP:${IP},POST:${PORT}`);
            return [IP, PORT];
        }
    });
    list = list.filter( el => el );
    console.log(list);
};
// connect Proxy
const requestProxy = options =>{
    return new Promise(resolve =>{
        request(options,(err, response, body) =>{
            if (err || !body) {
                throw err;
            } else {
                //console.log(body);
                loadHtml(body);
                resolve();
            }
        })
    })
};
ipUrl();
