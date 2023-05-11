linters:
	black .
	isort .
	mypy src tests server.py lambda/lambda.py
	flake8 src tests server.py lambda/lambda.py

up:
	docker compose up --build -d
