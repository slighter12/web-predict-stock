const MongoClient = require('mongodb').MongoClient;

MongoClient.connect('mongodb://localhost:27017', { useNewUrlParser: true }, (err, database) =>{
    console.log('mongodb is connecting!');
    if (err) throw err;
    // process database
    const db = database.db('testdb');
    db.collection('testdb', (err,collection) =>{
        collection.insert({id:1, firstName:'Steve', lastName:'Jobs'});
        collection.count((err, count) =>{
            if (err) throw  err;
            console.log(`Total Rows: ${count}`);
        });
    });
    database.close();
});