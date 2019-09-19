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
function isValidDate(argvIn){
    if (argvIn){
        let time = moment(argvIn.replace(/\//g,'-'));
        //console.log(time);
        if (!time.isValid()) throw new Error(argvIn + ' input date type is error!');
        return moment(time);
    }
}
const durationStart = isValidDate(startDate).startOf('month');
const durationEnd = isValidDate(stopDate).endOf('month');
if (codeIDs){
    for (let x = 0; x < codeIDs.length; x++){
        let Id = codeIDs[x];
        let patternSii = /^sii\d{2}$/;
        let patternId = /^\d{4}$/;
        if (Id.match(patternSii)){
            //todo: get mongodb sii list
        }
        if (Id.match(patternId)){
            let timePointer = durationEnd;
            if (moment().isBefore(durationEnd)) {
                requestHistory(moment().format('YYYYMMDD'), Id);
                timePointer.add(-1, 'month');
                let tag = {
                    code: Id,
                    endDate:moment().format('YYYY-MM-DD')
                };
            }
            (async ()=> {
                while (durationStart.isBefore(timePointer)) {
                    requestHistory(timePointer.format('YYYYMMDD'), Id);
                    timePointer = timePointer.add(-1, 'month');
                    await sleep(3000);
                }
            })();
        }
    }
}

function requestHistory(date,id) {
    let url = `https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=${date}&stockNo=${id}`;
    //console.log(url);
    request(url, (err, response, body) => {
        if (err || !body) {
            console.log(err);
        } else {
            let data = JSON.parse(body).data;
            if (data){
                return undefined;
            }
            for (let x = 0; x < data.length; x++){
                let dayInfo = data[x];
                let result = {
                    code: id,
                    date: dayInfo[0],
                    Volume: dayInfo[1],
                    TurnOver: dayInfo[2],
                    open: dayInfo[3],
                    height: dayInfo[4],
                    low: dayInfo[5],
                    close: dayInfo[6],
                    volatility: dayInfo[7],
                    TransactionsNumber: dayInfo[8],
                };
                //console.log(result);
                upsertDb({code: result.code, date: result.date}, result, 'stock-history');
            }
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
        client.close();
    }
}
