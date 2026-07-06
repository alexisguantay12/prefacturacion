import pyodbc

from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model

from applications.entidades.models import Paciente


def limpiar_texto(valor):
    if valor is None:
        return None
    valor = str(valor).strip()
    return valor if valor else None


def limpiar_nombre(valor):
    valor = limpiar_texto(valor)
    return valor.title() if valor else ""


def limpiar_dni(valor):
    valor = limpiar_texto(valor)
    if not valor:
        return None

    return (
        valor.replace(".", "")
        .replace("-", "")
        .replace(" ", "")
        .strip()
    )


def limpiar_genero(valor):
    valor = limpiar_texto(valor)

    if not valor:
        return None

    valor = valor.upper()

    if valor in ["M", "MASCULINO", "HOMBRE", "VARON"]:
        return "Masculino"

    if valor in ["F", "FEMENINO", "MUJER"]:
        return "Femenino"

    return None


class Command(BaseCommand):
    help = "Migra pacientes desde SQL Server HCE.dbo.Personas hacia Paciente"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--confirm", action="store_true")
        parser.add_argument("--limit", type=int)
        parser.add_argument("--usuario", type=str)
        parser.add_argument("--batch-size", type=int, default=1000)

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        confirm = options["confirm"]
        limit = options["limit"]
        usuario_username = options["usuario"]
        batch_size = options["batch_size"]

        if not dry_run and not confirm:
            self.stdout.write(self.style.ERROR(
                "Usá --dry-run para probar o --confirm para migrar en serio."
            ))
            return

        usuario_migracion = None

        if usuario_username:
            User = get_user_model()

            try:
                usuario_migracion = User.objects.get(username=usuario_username)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"No existe el usuario: {usuario_username}"
                ))
                return

        conn_str = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=192.168.180.254,1433;"
            "DATABASE=HCE;"
            "UID=UsrSantaClaraRead;"
            "PWD=5@nt@k1@r@;"
            "TrustServerCertificate=yes;"
        )

        top = f"TOP {limit}" if limit else ""

        sql = f"""
            SELECT {top}
                p.Nombres,
                p.Apellido,
                p.Sexo,
                p.FechaNacimiento,
                p.Documento_Numero,
                p.TelefonoCelular,
                CASE
                    WHEN NULLIF(LTRIM(RTRIM(p.Domicilio_Calle)), '') IS NOT NULL
                     AND NULLIF(LTRIM(RTRIM(l.Nombre)), '') IS NOT NULL
                        THEN LTRIM(RTRIM(p.Domicilio_Calle)) + ', ' + LTRIM(RTRIM(l.Nombre))
                    WHEN NULLIF(LTRIM(RTRIM(p.Domicilio_Calle)), '') IS NOT NULL
                        THEN LTRIM(RTRIM(p.Domicilio_Calle))
                    WHEN NULLIF(LTRIM(RTRIM(l.Nombre)), '') IS NOT NULL
                        THEN LTRIM(RTRIM(l.Nombre))
                    ELSE ''
                END AS Domicilio,
                prov.Nombre AS Provincia,
                pais.Nombre AS Pais
            FROM dbo.Personas p
            LEFT JOIN Localidades l
                ON l.Id = p.Domicilio_IdLocalidad
            LEFT JOIN Provincias prov
                ON prov.Id = p.Domicilio_IdProvincia
            LEFT JOIN Paises pais
                ON pais.Id = p.Domicilio_IdPais
            WHERE p.Apellido NOT LIKE '%prueba%'
              AND p.Nombres NOT LIKE '%prueba%'
              AND p.Estado = 'A'
              AND p.Documento_Numero IS NOT NULL
        """

        creados = 0
        actualizados = 0
        omitidos = 0
        errores = 0
        procesados = 0

        self.stdout.write("Conectando a SQL Server...")

        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute(sql)

        try:
            with transaction.atomic():
                while True:
                    filas = cursor.fetchmany(batch_size)

                    if not filas:
                        break

                    columnas = [col[0] for col in cursor.description]

                    for fila in filas:
                        data = dict(zip(columnas, fila))
                        procesados += 1

                        try:
                            dni = limpiar_dni(data.get("Documento_Numero"))

                            if not dni:
                                omitidos += 1
                                continue

                            defaults = {
                                "nombre": limpiar_nombre(data.get("Nombres")),
                                "apellido": limpiar_nombre(data.get("Apellido")),
                                "fecha_nacimiento": data.get("FechaNacimiento"),
                                "genero": limpiar_genero(data.get("Sexo")),
                                "telefono": limpiar_texto(data.get("TelefonoCelular")),
                                "direccion": limpiar_texto(data.get("Domicilio")),
                                "provincia": limpiar_texto(data.get("Provincia")),
                                "nacionalidad": limpiar_texto(data.get("Pais")),
                            }

                            if usuario_migracion:
                                defaults["user_updated"] = usuario_migracion

                            paciente = Paciente.objects.filter(dni=dni).first()

                            if paciente:
                                for campo, valor in defaults.items():
                                    setattr(paciente, campo, valor)

                                paciente.save()
                                actualizados += 1
                            else:
                                if usuario_migracion:
                                    defaults["user_made"] = usuario_migracion 
                                Paciente.objects.create(
                                    dni=dni,
                                    **defaults
                                )
                                creados += 1

                        except Exception as e:
                            errores += 1
                            self.stdout.write(self.style.ERROR(
                                f"Error procesando DNI {data.get('Documento_Numero')}: {e}"
                            ))

                    self.stdout.write(
                        f"Procesados: {procesados} | Creados: {creados} | "
                        f"Actualizados: {actualizados} | Omitidos: {omitidos} | Errores: {errores}"
                    )

                if dry_run:
                    raise Exception("DRY RUN: rollback intencional")

        except Exception as e:
            if dry_run:
                self.stdout.write(self.style.WARNING(
                    "Dry-run finalizado. No se guardó nada."
                ))
            else:
                raise e

        finally:
            cursor.close()
            conn.close()

        self.stdout.write(self.style.SUCCESS(
            f"Finalizado | Procesados: {procesados} | Creados: {creados} | "
            f"Actualizados: {actualizados} | Omitidos: {omitidos} | Errores: {errores}"
        ))


