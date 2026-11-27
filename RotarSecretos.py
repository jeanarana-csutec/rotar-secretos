import boto3
import pymysql
import json
import secrets


def lambda_handler(event, context):
    sm = boto3.client("secretsmanager")
    ssm = boto3.client("ssm")
    connection = None

    try:
        # Obtener las credenciales del administrador
        response = sm.get_secret_value(
            SecretId="rds_mysql_alumnos/admin"
        )
        admin = json.loads(response["SecretString"])

        connection = pymysql.connect(
            host=admin["host"],
            port=int(admin.get("port", 3306)),
            user=admin["username"],
            password=admin["password"],
            connect_timeout=5,
            autocommit=True
        )

        # Guardar el host donde tu Lambda de listar lo busca
        ssm.put_parameter(
            Name="/rds_mysql_alumnos/punto_enlace",
            Value=admin["host"],
            Type="String",
            Overwrite=True
        )

        with connection.cursor() as cursor:
            for ambiente in ["dev", "test", "prod"]:

                # Leer el secreto del ambiente
                nombre_secreto = f"rds_mysql_alumnos/{ambiente}"
                response = sm.get_secret_value(
                    SecretId=nombre_secreto
                )
                datos = json.loads(response["SecretString"])

                # Generar una contraseña diferente para cada usuario
                nueva_password = "Aa1!" + secrets.token_urlsafe(18)

                # Cambiar la contraseña en MySQL
                cursor.execute(
                    "ALTER USER %s@%s IDENTIFIED BY %s",
                    (datos["username"], "%", nueva_password)
                )

                # Guardar la contraseña en Parameter Store
                ssm.put_parameter(
                    Name=f"/rds_mysql_alumnos/user_{ambiente}/password",
                    Value=nueva_password,
                    Type="SecureString",
                    Overwrite=True
                )

                # Actualizar también el secreto existente
                datos["password"] = nueva_password

                sm.put_secret_value(
                    SecretId=nombre_secreto,
                    SecretString=json.dumps(datos)
                )

                print(f"Rotacion completada: {datos['username']}")

        return {
            "statusCode": 200,
            "body": "Claves actualizadas para dev, test y prod"
        }

    finally:
        if connection is not None:
            connection.close()