linters:
	black .
	isort .
	mypy smarthouse example server.py lambda/lambda.py
	flake8 smarthouse example server.py lambda/lambda.py

up:
	docker compose up --build -d

build_py:
	python3 setup.py pytest
	python3 setup.py sdist bdist_wheel

upload_py:
	twine upload dist/*
