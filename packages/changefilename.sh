#!/bin/bash
find . -type f | while read filename
do
    newname=`echo "$filename" | tr '[:upper:]' '[:lower:]'`
    mv "$filename" "$newname"
done