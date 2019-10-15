const MongoClient = require('mongodb').MongoClient,
    dburi = 'mongodb://localhost:27017';
const origineDbUrl = `${dburi}/Stock`,
    preprocessDbUrl = `${dburi}/preData`;

(async () => {
    const list = [];
    list.push(...await SaveSiiList());
    await upsertDb({key: 'sii-list'}, {key: 'sii-list', list}, 'stock-info');
    for (let codeid of list) {
        await createBasicData(codeid);
        process.stdout.write(`\rcode ID: ${codeid}`);
    }
    console.log('\nfinish');
})();

async function SaveSiiList() {
    let client;
    const siiList = [],
        codeIDs=[];
    try {
        client = await MongoClient.connect(origineDbUrl, {useNewUrlParser: true, useUnifiedTopology: true});
        let db = client.db();
        siiList.push(...await db.collection('stock-info').find().toArray());
    } catch (err) {
        console.log(err.stack);
    }
    if (client) {
        await client.close();
    }
    for (let list of siiList) {
        for (let Id of Object.keys(list.list)) {
            codeIDs.push(Id);
        }
    }
    return [... new Set(codeIDs)];
}

async function upsertDb(key, data, dbName) {
    let client;
    try {
        client = await MongoClient.connect(preprocessDbUrl, {useNewUrlParser: true, useUnifiedTopology: true});
        let db = client.db();
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

async function createBasicData(code) {
    let client;
    const table = [...Array(9)].map(x=>[]);
    try {
        client = await MongoClient.connect(origineDbUrl, {useNewUrlParser: true, useUnifiedTopology: true});
        let db = client.db();
        let docs = await db.collection('stock-history').find({code}).sort({date: 1}).toArray();
        for (let obj of docs) {
            for (let value of obj.data) {
                for (let x = 0; x < 9; x++) {
                    table[x].push(value[x]);
                }
            }
        }
        const dataObj = {
            code,
            dates: table[0].reverse(),
            volume: table[1].reverse(),
            turnover: table[2].reverse(),
            openPrice: table[3].reverse(),
            highPrice: table[4].reverse(),
            lowPrice: table[5].reverse(),
            closePrice: table[6].reverse(),
            quoteChange: table[7].reverse(),
            transaction: table[8].reverse()
        };
        await upsertDb({code}, dataObj, 'stock-info');
    } catch (err) {
        console.log(code);
    }
    if (client) {
        await client.close();
    }
}
