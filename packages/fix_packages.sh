!/bin/bash
find . -type f -name "*.yaml" | while read filename
do
  sed -i '1d' "$filename"
  sed -i 's/^  //' "$filename"
done
