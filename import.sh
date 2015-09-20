#!/usr/bin/env bash
pv data/comments.csv | sudo -u postgres psql hnews -c "COPY comments FROM STDIN DELIMITER ',' CSV"
pv data/posts.csv | sudo -u postgres psql hnews -c "COPY posts FROM STDIN DELIMITER ',' CSV"
sudo -u postgres psql hnews -c "UPDATE posts SET all_kids=NULL";