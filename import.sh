pv data/comments.csv | sudo -u postgres psql hnews -c "COPY comments FROM STDIN DELIMITER ',' CSV"
pv data/posts.csv | sudo -u postgres psql hnews -c "COPY posts FROM STDIN DELIMITER ',' CSV"