#!/bin/bash
git rm -r --cached .
git add .
git status

echo -n "Enter the Description for the Change: "   
read CHANGE_MSG

git commit -m " ${CHANGE_MSG}"
git push origin master
exit
