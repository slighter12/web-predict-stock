const request = require('request');
const moment = require('moment');
//todo: change old async await setTimeout function
const {promisify} = require('util');
//const sleep = promisify( (ms,cb) => setTimeout(cb,ms) );
const sleep = promisify(setTimeout);
const MongoClient = require('mongodb').MongoClient,
    dburi = 'mongodb://localhost:27017';
//startDate need after 2010-01-04
//todo: data must be changed, check website
//https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=20000301&stockNo=1101
let [startDate, stopDate, ...codeIDs] = process.argv.slice(2);
const duration = getDurationDate(startDate,stopDate);

if ( Array.isArray(codeIDs) && codeIDs.length ) {
    (async ()=> {
        for (let date of duration) {
            for (let x = 0; x < codeIDs.length; x++){
                let Id = codeIDs[x];
                let patternSii = /^sii\d{2}$/;
                let patternId = /^\d{4}$/;
                if (Id.match(patternSii)){
                    //todo: get mongodb sii list
                }
                if (Id.match(patternId)){
                    requestHistory(date, Id);
                    await sleep(3000);
                }
            }
        }
    })();
} else {
    // get all stock history data
    (async () => {
        const idList = await getSiiList();
        for (let list of idList) {
            for (let Id of Object.keys(list.list)) {
                codeIDs.push(Id);
            }
        }
        codeIDs.filter((item, index) => codeIDs.indexOf(item) === index);
        for (let date of duration) {
            for (let Id of codeIDs) {
                if (!await checkDataExist(date, Id)){
                    requestHistory(date, Id);
                    await sleep(3000);
                }
            }
        }
    })();
}

function getDurationDate(startDate, stopDate) {
    const durationStart = !startDate ? moment("2010-01-31") : isValidDate(startDate);
    const durationEnd = !stopDate ? moment() : isValidDate(stopDate);
    const dateList = [];
    let timePointer = durationEnd;
    dateList.push(timePointer.format('YYYYMMDD'));
    timePointer.add(-1, 'month').endOf('month');
    while (!timePointer.isBefore(durationStart)) {
        dateList.push(timePointer.format('YYYYMMDD'));
        timePointer.add(-1, 'month').endOf('month');
    }
    return dateList;
}

function isValidDate(argvIn){
    let time = moment(argvIn.replace(/\//g,'-'));
    if (!time.isValid()) throw new Error(argvIn + ' input date type is error!');
    if (moment().isBefore(time)) return moment();
    if (moment(time).isBefore("2010-01-31")) return moment("2010-01-31");
    return moment(time).endOf('month');
}

function requestHistory(date, id) {
    let url = `https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=${date}&stockNo=${id}`;
    //console.log(url);
    request(url, (err, response, body) => {
        if (err || !body) {
            console.log(err);
        } else {
            //console.log(JSON.parse(body));
            let data = JSON.parse(body);
            if (!data.data) {
                return data;
            }
            let result = {
                code: id,
                date: data.date,
                data: data.data
            };
            //console.log(result);
            upsertDb({code: result.code, date: result.date}, result, 'stock-history').then();
        }
    });
}

async function upsertDb(key, data, dbName) {
    const url = `${dburi}/Stock`;
    let client;
    try {
        client = await MongoClient.connect(url, {useNewUrlParser: true, useUnifiedTopology: true});
        let db = client.db('Stock');
        let mongoOps = [{
            updateOne: {
                filter: key,
                update: data,
                upsert: true
            }
        }];
        db.collection(dbName).bulkWrite(mongoOps, err => {
            if (err) throw err
        });
    } catch (err) {
        console.log(err.stack);
    }
    if (client) {
        await client.close();
    }
}

async function getSiiList(siicode) {
    const url = `${dburi}/Stock`;
    let client;
    const list = [];
    if (!siicode){
        try {
            client = await MongoClient.connect(url, {useNewUrlParser: true, useUnifiedTopology: true});
            let db = client.db('Stock');
            list.push(...await db.collection('stock-info').find().toArray());
        } catch (err) {
            console.log(err.stack);
        }
    }
    if (client) {
        await client.close();
    }
    return list;
}

async function checkDataExist(date, code) {
    const url = `${dburi}/Stock`;
    let client, work;
    try {
        client = await MongoClient.connect(url, {useNewUrlParser: true, useUnifiedTopology: true});
        let db = client.db('Stock');
        console.log({date,code});
        db.collection('stock-history').find({date, code}).toArray((err,items) => {
            if (err) throw err;
            work = items.length;
        });
    } catch (err) {
        console.log(err.stack);
    }
    if (client) {
        await client.close();
    }
    return work;
}
