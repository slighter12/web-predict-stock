const path = require('path');
//const webpack = require('webpack');
const nodeExternals = require('webpack-node-externals');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');

const serverConfig = {
    entry: {
        server: './server.js'
    },
    output: {
        path: path.join(__dirname, 'dist'),
        filename: '[name].js'
    },
    target: 'node',
    externals: [nodeExternals()],
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

const clientConfig = {
    mode: 'development',
    entry: {
        index: './src/index.js'
    },
    output: {
        path: path.join(__dirname, 'dist'),
        filename: '[name].bundle.js'
    },
    target: 'web',
    devServer: {
        contentBase: './dist'
    },
    module: {
        rules: [
        {
            test: /\.js$/,
            exclude: /node_module/,
            loader: 'babel-loader',
        },
        {
            test: /\.pug$/,
            use: [ 'html-loader', 'pug-html-loader' ],
        },
        {
            test: /\.(scss|sass)$/,
            use: [ 'style-loader', MiniCssExtractPlugin.loader, 'css-loader', 'sass-loader' ],
        }
        ]
    },
    plugins: [
        new HtmlWebpackPlugin({
            template: './src/index.pug',
            filename: 'index.html',
        }),
        new MiniCssExtractPlugin({
            filename: 'app.css'
        })
    ]
};

module.exports = [ clientConfig ];
