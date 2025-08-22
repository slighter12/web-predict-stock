const axios = require('axios');
const fs = require('fs');
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
                    if (!await checkDataExist(date, Id)) {
                        await requestHistory(date, Id);
                        await sleep(3000);
                    }
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
        codeIDs = [...new Set(codeIDs)];
        for (let date of duration) {
            for (let Id of codeIDs) {
                if (!await checkDataExist(date, Id)){
                    await requestHistory(date, Id);
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
    if (moment().isSame(time, 'month')) return time;
    return moment(time).endOf('month');
}

async function requestHistory(date, id) {
    let url = `https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=${date}&stockNo=${id}`;
    //console.log(url);
    try {
        const response = await axios.get(url);
        const body = response.data;
        //console.log(JSON.parse(body));
        let data = body;
        if (!data.data) {
            return data;
        }
        fs.writeFileSync(`data/${id}-${date}`, JSON.stringify(body));
        let result = {
            code: id,
            date: data.date,
            data: data.data
        };
        //console.log(result);
        await upsertDb({code: result.code, date: result.date}, result, 'stock-history');
    } catch (err) {
        console.log(err);
    }
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
        process.stdout.write(`\rDate: ${date}, code ID: ${code}`);
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
