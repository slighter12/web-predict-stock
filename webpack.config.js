const path = require('path');
//const webpack = require('webpack');
const nodeExternals = require('webpack-node-externals');
const HtmlWebpackPlugin = require('html-webpack-plugin');

/*const serverConfig = {
    entry: {
        server: './server.js'
    },
    output: {
        path: path.join(__dirname, 'dist'),
        filename: '[name].js'
    },
    target: 'node',
    node: {
        __dirname: false,
        __filename: false
    },
    module: {
        rules: [
        {
            test: /.js$/,
            exclude: /node_modules/,
            loader: 'babel-loader',
            options: {
                presets: ['@babel/preset-env']
            },
        }]
    },
};
*/
const clientConfig = {
    entry: {
        index: './src/index.js'
    },
    output: {
        path: path.join(__dirname, 'dist'),
        filename: '[name].js'
    },
    externals: [nodeExternals()],
    target: 'web',
    module: {
        rules: [
        {
            test: /.js$/,
            exclude: /node_module/,
            loader: 'babel-loader',
        },
        {
            test: /.pug$/,
            use: [ 'html-loader', 'pug-html-loader' ],
        }
        ]
    },
    plugins: [
        new HtmlWebpackPlugin({
            template: './src/index.pug',
            filename: 'index.html',
        })
    ]
};

//module.exports = [ serverConfig, clientConfig ];
module.exports = [clientConfig];
