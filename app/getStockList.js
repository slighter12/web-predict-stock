const request = require('request');
const MongoClient = require('mongodb').MongoClient,
    dburi = 'mongodb://localhost:27017';

const useragent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36';
const data = 'encodeURIComponent=1&TYPEK=sii&step=1&firstin=1&';
const headers = {
    'User-Agent': useragent,
    'Content-Length': 62,
    'Content-Type': 'application/x-www-form-urlencoded'
};

async function getAllStockId() {
    for(let id = 1; id < 36; id++) {
        let codeId = id.toString().padStart(2, '0');
        let options = {
            method: 'POST',
            uri: 'https://mops.twse.com.tw/mops/web/ajax_t123sb09',
            headers: headers,
            body: `${data}code=${codeId}&slt=${codeId}`,
        };
        request(options, (err, response, body) => {
            if (err || !body) {
                console.log(err);
            } else {
                //console.log(body);
                //console.log(response.statusCode);
                console.log(`running sii ${codeId}`);
                let stockDb = {};
                //todo: using cheerio to get stock id list
                let pattern = /<td rowspan=['"]2['"]>(.*?)<\/td>/g;
                let preMatchArray = body.match( pattern );
                if (preMatchArray) {
                    preMatchArray.filter((word, index) => {
                        let stockID = word.match(/>(\d{4,6})</);
                        if (stockID) {
                            stockDb[stockID[1]] = preMatchArray[index + 1].match(/>(.*?)</)[1];
                        }
                    });
                    upsertDb({sii: codeId}, { sii: codeId, list: stockDb }, 'stock-info');
                }
                //console.log(stockDb);
            }
        });
        await sleep(3000);
    }
}
function sleep(ms){
    return new Promise(resolve => {
        setTimeout(resolve, ms);
    })
}

async function upsertDb(key, data, dbName) {
    await MongoClient.connect(dburi, { useNewUrlParser: true, useUnifiedTopology: true }, (err, database) => {
        if (err) throw err;
        let db = database.db('Stock');
        let mongoOps = [{
            updateOne: {
                filter: key,
                update: data,
                upsert: true
            }
        }];
        db.collection(dbName).bulkWrite(mongoOps, err => {
            if (err) throw err;
        });
        database.close();
    })
}
getAllStockId();