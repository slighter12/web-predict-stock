const axios = require('axios');
const cheerio = require('cheerio');
const fs = require('fs');
const path = require('path');

const useragent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36';

class Options {
    constructor(url, method, data) {
        this.url = url;
        this.method = method;
        this.headers = {
            'User-Agent': useragent,
        };
        if (data) {
            this.data = data;
        }
    }
}

// 使用JSON文件存儲代理數據
const PROXY_FILE = path.join(__dirname, 'proxy-list.json');

const loadProxies = () => {
    try {
        if (fs.existsSync(PROXY_FILE)) {
            return JSON.parse(fs.readFileSync(PROXY_FILE, 'utf8'));
        }
    } catch (err) {
        console.error('Error loading proxy file:', err);
    }
    return [];
};

const saveProxies = (proxies) => {
    try {
        fs.writeFileSync(PROXY_FILE, JSON.stringify(proxies, null, 2));
    } catch (err) {
        console.error('Error saving proxy file:', err);
    }
};

const insertProxy = (ip, port, type) => {
    const proxies = loadProxies();
    const newProxy = { ip, port, type, timestamp: new Date().toISOString() };
    
    // 避免重複
    const exists = proxies.some(p => p.ip === ip && p.port === port);
    if (!exists) {
        proxies.push(newProxy);
        saveProxies(proxies);
        console.log(`Added proxy: ${ip}:${port} (${type})`);
    }
};

// proxy website
const ipUrl = async () => {
    //this uri will ban my ip, need fix
    //let options = new Options('http://free-proxy.cz/zh/proxylist/country/TW/all/ping/level1', 'POST',
    //    {country: 'TW', protocol: 'all', anonymity: 'level1', send: '过滤器的代理服务器'});
    let options = new Options('http://www.aliveproxy.com/proxy-list/proxies.aspx/Taiwan-tw', 'GET');
    //console.log(options);
    await requestProxy(options);
};

//access proxy data from website
const loadHtml = (data) => {
    let $ = cheerio.load(data);
    let pattern = /\d*?\.\d*?\.\d*?\.\d*?:\d*?.*?((High anonymity)|(Anonymous))/g;
    let patternIP = /(\d{1,3})\.(\d{1,3}\.\d{1,3}\.\d{1,3}):(\d*?)-/;
    let list = $('tr.cw-list').get().map(repo => {
        let $repo = $(repo);
        let content = $repo.text();
        if (content.match(pattern)) {
            let word = content.match(patternIP);
            if (word) {
                let IP = `${word[1]}.${word[2]}`;
                let PORT = word[3].replace(new RegExp(word[1]), '');
                // console.log(`IP:${IP},POST:${PORT}`);
                return [IP, PORT];
            }
        }
    });
    list = list.filter(el => el);
    console.log('Found proxies:', list);
    
    // 保存到JSON文件
    list.forEach(([ip, port]) => {
        insertProxy(ip, port, 'High anonymity');
    });
};

// connect Proxy
const requestProxy = async (options) => {
    try {
        const response = await axios(options);
        const body = response.data;
        //console.log(body);
        loadHtml(body);
    } catch (err) {
        console.error('Error fetching proxy list:', err);
    }
};

ipUrl();
