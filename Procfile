release: python manage.py collectstatic --noinput && python manage.py migrate
web: gunicorn meebun_erp.wsgi:application --workers 3 --timeout 60