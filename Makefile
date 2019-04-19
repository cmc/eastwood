image:
	docker build -t eastwood:latest .
clean:
	rm -rvf postgres-data/
	docker build --no-cache -t eastwood:latest .
compose:
	docker-compose down
	docker-compose up
