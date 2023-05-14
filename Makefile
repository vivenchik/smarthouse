linters:
	black .
	isort .
	mypy home example server.py lambda/lambda.py
	flake8 home example server.py lambda/lambda.py

up:
	docker compose up --build -d
