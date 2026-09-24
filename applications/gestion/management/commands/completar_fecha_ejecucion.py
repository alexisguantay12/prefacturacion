from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Min, Q

from applications.gestion.models import OrdenAutorizacion


class Command(BaseCommand):

    help = (
        "Completa fecha_ejecucion de órdenes autorizadas históricas "
        "utilizando la menor fecha_desde de sus detalles y, si no existe, "
        "la fecha de la orden."
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Muestra qué órdenes se modificarían "
                "sin guardar cambios."
            ),
        )

    def handle(self, *args, **options):

        dry_run = options["dry_run"]

        self.stdout.write("")
        self.stdout.write(
            self.style.NOTICE(
                "Buscando órdenes autorizadas sin fecha de ejecución..."
            )
        )

        # ---------------------------------------------------------------------
        # ÓRDENES HISTÓRICAS A COMPLETAR
        # ---------------------------------------------------------------------

        ordenes = (
            OrdenAutorizacion.objects
            .filter(
                autorizada=True,
                estado="autorizada",
                fecha_ejecucion__isnull=True,
                deleted_at__isnull=True,
            )
            .annotate(
                fecha_detalle_min=Min(
                    "detalles__fecha_desde",
                    filter=Q(
                        detalles__fecha_desde__isnull=False,
                        detalles__deleted_at__isnull=True,
                    ),
                )
            )
            .order_by("id")
        )

        total = ordenes.count()

        if total == 0:

            self.stdout.write(
                self.style.SUCCESS(
                    "No hay órdenes autorizadas pendientes de completar."
                )
            )

            return

        self.stdout.write(
            f"Órdenes encontradas: {total}"
        )

        self.stdout.write("")

        ordenes_actualizar = []

        sin_fecha = 0
        desde_detalle = 0
        desde_orden = 0

        # ---------------------------------------------------------------------
        # CALCULAR FECHA DE EJECUCIÓN
        # ---------------------------------------------------------------------

        for orden in ordenes.iterator(
            chunk_size=500
        ):

            # Misma lógica que fecha_ejecucion_sugerida:
            #
            # 1. menor fecha_desde de los detalles
            # 2. si no existe, orden.fecha

            fecha_ejecucion = (
                orden.fecha_detalle_min
                or orden.fecha
            )

            # -------------------------------------------------------------
            # NO HAY NINGUNA FECHA POSIBLE
            # -------------------------------------------------------------

            if not fecha_ejecucion:

                sin_fecha += 1

                self.stdout.write(
                    self.style.WARNING(
                        f"Orden #{orden.id}: "
                        "sin fecha_desde y sin fecha de orden. "
                        "No se modifica."
                    )
                )

                continue

            # -------------------------------------------------------------
            # ORIGEN DE LA FECHA
            # -------------------------------------------------------------

            if orden.fecha_detalle_min:

                origen = "detalle.fecha_desde"
                desde_detalle += 1

            else:

                origen = "orden.fecha"
                desde_orden += 1

            orden.fecha_ejecucion = fecha_ejecucion

            ordenes_actualizar.append(
                orden
            )

            self.stdout.write(
                f"Orden #{orden.id:06d} -> "
                f"{fecha_ejecucion.strftime('%d/%m/%Y')} "
                f"({origen})"
            )

        # ---------------------------------------------------------------------
        # DRY RUN
        # ---------------------------------------------------------------------

        if dry_run:

            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN: no se realizó ningún cambio en la base de datos."
                )
            )

            self._mostrar_resumen(
                total=total,
                actualizar=len(ordenes_actualizar),
                desde_detalle=desde_detalle,
                desde_orden=desde_orden,
                sin_fecha=sin_fecha,
            )

            return

        # ---------------------------------------------------------------------
        # GUARDAR
        # ---------------------------------------------------------------------

        if ordenes_actualizar:

            with transaction.atomic():

                OrdenAutorizacion.objects.bulk_update(
                    ordenes_actualizar,
                    [
                        "fecha_ejecucion",
                    ],
                    batch_size=500,
                )

        # ---------------------------------------------------------------------
        # RESULTADO
        # ---------------------------------------------------------------------

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "Proceso finalizado correctamente."
            )
        )

        self._mostrar_resumen(
            total=total,
            actualizar=len(ordenes_actualizar),
            desde_detalle=desde_detalle,
            desde_orden=desde_orden,
            sin_fecha=sin_fecha,
        )

    def _mostrar_resumen(
        self,
        total,
        actualizar,
        desde_detalle,
        desde_orden,
        sin_fecha,
    ):

        self.stdout.write("")
        self.stdout.write("========================================")
        self.stdout.write("RESUMEN")
        self.stdout.write("========================================")

        self.stdout.write(
            f"Órdenes encontradas:        {total}"
        )

        self.stdout.write(
            f"Órdenes completadas:        {actualizar}"
        )

        self.stdout.write(
            f"Desde fecha_desde:          {desde_detalle}"
        )

        self.stdout.write(
            f"Desde orden.fecha:          {desde_orden}"
        )

        self.stdout.write(
            f"Sin ninguna fecha posible:  {sin_fecha}"
        )

        self.stdout.write(
            "========================================"
        )