from django.urls import reverse

from rest_framework import serializers

from django_resaas.engine.core.base.serializers import BaseSerializer

from saude.models.resultadoexamemedico import ResultadoExameMedico


class ResultadoExameMedicoSerializer(BaseSerializer):

    ############################################################
    # PROPRIEDADES DO MODELO
    ############################################################

    is_folder = serializers.ReadOnlyField()
    is_file = serializers.ReadOnlyField()

    children_count = serializers.ReadOnlyField()
    has_children = serializers.ReadOnlyField()

    ############################################################
    # METADADOS DO FICHEIRO
    ############################################################

    filename = serializers.SerializerMethodField()
    extension = serializers.SerializerMethodField()
    icon = serializers.SerializerMethodField()
    size_human = serializers.SerializerMethodField()
    
    ############################################################
    # NAVEGAÇÃO
    ############################################################

    breadcrumb = serializers.SerializerMethodField()

    class Meta:

        model = ResultadoExameMedico

        fields = "__all__"

    ############################################################
    # FICHEIRO
    ############################################################

    def get_filename(self, obj):

        if not obj.file:
            return None

        return obj.file.name.split("/")[-1]

    def get_extension(self, obj):

        if not obj.file:
            return None

        return obj.extensao

    def get_icon(self, obj):

        if obj.is_folder:
            return "folder"

        ext = (obj.extensao or "").lower()

        if ext == ".pdf":
            return "picture_as_pdf"

        if ext in [
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".bmp",
            ".webp",
        ]:
            return "image"

        if ext in [
            ".doc",
            ".docx",
        ]:
            return "description"

        if ext in [
            ".xls",
            ".xlsx",
        ]:
            return "table_view"

        if ext in [
            ".zip",
            ".rar",
            ".7z",
        ]:
            return "folder_zip"

        return "insert_drive_file"

    def get_size_human(self, obj):

        tamanho = obj.tamanho or 0

        for unidade in ["B", "KB", "MB", "GB", "TB"]:

            if tamanho < 1024:
                return f"{tamanho:.1f} {unidade}"

            tamanho /= 1024

        return f"{tamanho:.1f} PB"

    ############################################################
    # URLS
    ############################################################

    def get_preview_url(self, obj):

        request = self.context.get("request")

        if not request:
            return None

        if obj.is_folder:
            return None

        return request.build_absolute_uri(

            reverse(

                "resultadoexamemedico-preview",

                args=[obj.pk],

            )

        )

    def get_download_url(self, obj):

        request = self.context.get("request")

        if not request:
            return None

        if obj.is_folder:
            return None

        return request.build_absolute_uri(

            reverse(

                "resultadoexamemedico-download",

                args=[obj.pk],

            )

        )

    ############################################################
    # BREADCRUMB
    ############################################################

    def get_breadcrumb(self, obj):

        caminho = []

        pasta = obj.pai

        while pasta:

            caminho.insert(

                0,

                {

                    "id": pasta.id,

                    "nome": pasta.nome,

                }

            )

            pasta = pasta.pai

        return caminho