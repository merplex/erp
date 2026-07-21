release: python manage.py migrate
web: python manage.py collectstatic --noinput && gunicorn meebun_erp.wsgi:application --workers 3 --timeout 60