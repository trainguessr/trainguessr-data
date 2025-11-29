#!/bin/bash
mkdir -p ../cache/germany
cd ../cache/germany || exit
mkdir -p nodejs
docker run -v "$PWD/nodejs":/usr/src/app -w /usr/src/app node:latest bash -c "npm install db-stations"
mv nodejs/node_modules/db-stations/{data.json,full.json} .
rm -rf nodejs
cd - || exit