const path = require('path');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const HtmlWebpackPlugin = require('html-webpack-plugin');

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
        static: {
            directory: path.join(__dirname, 'dist'),
        },
        compress: true,
        port: 9000,
    },
    module: {
        rules: [
        {
            test: /\.js$/,
            exclude: /node_modules/,
            loader: 'babel-loader',
        },
        {
            test: /\.pug$/,
            use: [
                'html-loader',
                {
                    loader: 'pug-html-loader',
                    options: {
                        pretty: true
                    }
                }
            ],
        },
        {
            test: /\.(scss|sass)$/,
            use: [ 
                'style-loader', 
                MiniCssExtractPlugin.loader, 
                'css-loader', 
                'sass-loader' 
            ],
        }
        ]
    },
    plugins: [
        new MiniCssExtractPlugin({
            filename: 'app.css'
        }),
        new HtmlWebpackPlugin({
            template: './src/index.pug',
            filename: 'index.html',
        })
    ]
};

module.exports = [ clientConfig ];
