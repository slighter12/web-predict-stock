const fs = require('fs');
const moment = require('moment');
const MongoClient = require('mongodb').MongoClient,
    dburi = 'mongodb://localhost:27017';

const readDir = fs.readdirSync('./data');
//readDir.filter( word => word.match(/\d{4}-20\d{5}1/));
(async () => {
    for (let filename of readDir) {
        let data = fs.readFileSync(`./data/${filename}`);
        data = JSON.parse(data);
        data.date = moment(data.date).endOf('month').format('YYYYMMDD');
        let filepath = filename.replace(/2\d*?$/, data.date);
        let code = filepath.match(/^(\d{4})/)[0];
        let result = {
            code,
            date: data.date,
            data: data.data
        };
        //fs.writeFileSync(`data/${filepath}`, JSON.stringify(data));
        await upsertDb({code, date: result.date}, result, 'stock-history');
    }
})();

async function upsertDb(key, data, dbName) {
    let client;
    const url = `${dburi}/'Stock'`;
    try {
        client = await MongoClient.connect(url,{ useNewUrlParser: true, useUnifiedTopology: true });
        const db = client.db('Stock');
        let mongoOps = [{
            updateOne: {
                filter: key,
                update: data,
                upsert: true
            }
        }];
        db.collection(dbName).bulkWrite(mongoOps, err => { if (err) throw err });
    } catch (err) {
        console.log(err.stack);
    }
    if (client) {
        await client.close();
    }
}
