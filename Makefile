linters:
	black .
	isort .
	mypy src server.py lambda/lambda.py
	flake8 src server.py lambda/lambda.py

up:
	docker compose up --build -d
