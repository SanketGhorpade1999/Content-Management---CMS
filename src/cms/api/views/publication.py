import logging

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator

from cms.contexts.decorators import detect_language
from cms.contexts.models import WebPath

from cms.publications.forms import PublicationEditForm, PublicationForm
from cms.publications.models import Publication, PublicationContext
from cms.publications.serializers import (PublicationSerializer,
                                          PublicationContextSerializer,
                                          PublicationSelectOptionsSerializer)
from cms.publications.utils import publication_context_base_filter

from rest_framework import filters, generics
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.schemas.openapi import AutoSchema
from rest_framework.views import APIView

from . generics import UniCMSCachedRetrieveUpdateDestroyAPIView, UniCMSListCreateAPIView, UniCMSListSelectOptionsAPIView, check_locks
from . logs import ObjectLogEntriesList
from .. exceptions import LoggedPermissionDenied
from .. pagination import UniCmsApiPagination
from .. permissions import PublicationGetCreatePermissions
from .. serializers import UniCMSFormSerializer
from .. utils import check_user_permission_on_object


logger = logging.getLogger(__name__)


# TODO - better get with filters
class PublicationDetail(generics.RetrieveAPIView):
    name = 'publication-detail'
    description = 'News'
    queryset = Publication.objects.filter(is_active=True)
    # state='published')
    serializer_class = PublicationSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        for pub in super(PublicationDetail, self).get_queryset():
            # if pub.is_publicable:
            return pub


class ApiPublicationsByContextSchema(AutoSchema):
    def get_operation_id(self, path, method):# pragma: no cover
        return 'retrievePublicPublicationContext'


@method_decorator(detect_language, name='dispatch')
class ApiPublicationsByContext(generics.ListAPIView):
    """
    """
    description = 'ApiPublicationsByContext'
    pagination_class = UniCmsApiPagination
    serializer_class = PublicationContextSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['publication__title',
                     'publication__subheading',
                     'publication__content']
    schema = ApiPublicationsByContextSchema()
    # authentication_classes = [authentication.TokenAuthentication]
    # permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        query_params = publication_context_base_filter()
        query_params.update({'webpath__pk': self.kwargs['webpath_id']})
        category = self.request.GET.get('category')
        if category:
            query_params['publication__category__pk'] = category
        pubcontx = PublicationContext.objects.filter(**query_params)
        return pubcontx


class ApiPublicationsByContextCategorySchema(AutoSchema):
    def get_operation_id(self, path, method):# pragma: no cover
        return 'retrievePublicPublicationContextCategory'


@method_decorator(detect_language, name='dispatch')
class ApiPublicationsByContextCategory(ApiPublicationsByContext):
    schema = ApiPublicationsByContextCategorySchema()


@method_decorator(detect_language, name='dispatch')
class ApiContext(APIView): # pragma: no cover
    """
    """
    description = 'Get publications in Context (WebPath)'

    def get(self, request):
        webpaths = WebPath.objects.filter(is_active=True)
        pubs = ({i.pk: f'{i.site.domain}{i.get_full_path()}'}
                for i in webpaths if i.is_publicable)
        return Response(pubs)


class EditorialBoardPublicationsSchema(AutoSchema):
    def get_operation_id(self, path, method):# pragma: no cover
        if method == 'POST':
            return 'createEditorialBoardPublication'
        return 'listEditorialBoardPublications'


class PublicationList(UniCMSListCreateAPIView):
    """
    """
    description = ""
    search_fields = ['name', 'title', 'subheading', 'content']
    permission_classes = [PublicationGetCreatePermissions]
    serializer_class = PublicationSerializer
    queryset = Publication.objects.all()
    schema = EditorialBoardPublicationsSchema()


class EditorialBoardPublicationSchema(AutoSchema):
    def get_operation_id(self, path, method):# pragma: no cover
        if method == 'GET':
            return 'retrieveEditorialBoardPublication'
        if method == 'PATCH':
            return 'partialUpdateEditorialBoardPublication'
        if method == 'PUT':
            return 'updateEditorialBoardPublication'
        if method == 'DELETE':
            return 'deleteEditorialBoardPublication'


class PublicationView(UniCMSCachedRetrieveUpdateDestroyAPIView):
    """
    """
    description = ""
    permission_classes = [IsAdminUser]
    serializer_class = PublicationSerializer
    schema = EditorialBoardPublicationSchema()

    def get_object(self):
        pub_id = self.kwargs['pk']
        return get_object_or_404(Publication, pk=pub_id)

    def patch(self, request, *args, **kwargs):
        item = self.get_object()
        has_permission = item.is_editable_by(request.user)
        if not has_permission:
            raise LoggedPermissionDenied(classname=self.__class__.__name__,
                                         resource=request.method)
        # edit is_active params (only for owner or publisher)
        if item.is_active != request.data.get('is_active', item.is_active):
            if not item.is_publicable_by(request.user):
                raise LoggedPermissionDenied(classname=self.__class__.__name__,
                                             resource=request.method)
        return super().patch(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        item = self.get_object()
        has_permission = item.is_editable_by(request.user)
        if not has_permission:
            raise LoggedPermissionDenied(classname=self.__class__.__name__,
                                         resource=request.method)
        # edit is_active params (only for owner or publisher)
        if item.is_active != request.data.get('is_active', item.is_active):
            if not item.is_publicable_by(request.user):
                raise LoggedPermissionDenied(classname=self.__class__.__name__,
                                             resource=request.method)
        return super().put(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        item = self.get_object()
        permission = check_user_permission_on_object(request.user,
                                                     item, 'delete')
        if not permission['granted']:
            raise LoggedPermissionDenied(classname=self.__class__.__name__,
                                         resource=request.method)
        return super().delete(request, *args, **kwargs)


class EditorialBoardPublicationChangeStatusSchema(AutoSchema):
    def get_operation_id(self, path, method):# pragma: no cover
        return 'updateEditorialBoardPublicationStatus'


class PublicationChangeStateView(APIView):
    """
    """
    description = ""
    permission_classes = [IsAdminUser]
    serializer_class = PublicationSerializer
    schema = EditorialBoardPublicationChangeStatusSchema()

    def get_object(self):
        pub_id = self.kwargs['pk']
        return get_object_or_404(Publication, pk=pub_id)

    def get(self, request, *args, **kwargs):
        item = self.get_object()
        has_permission = item.is_publicable_by(request.user)
        if has_permission:
            check_locks(item, request.user)
            item.is_active = not item.is_active
            item.save()
            result = self.serializer_class(item)
            return Response(result.data)
        raise LoggedPermissionDenied(classname=self.__class__.__name__,
                                     resource=request.method)


# Abstract API classes for every related object of Publication

class PublicationRelatedObjectList(UniCMSListCreateAPIView):

    def get_data(self):
        """
        """
        pk = self.kwargs.get('publication_id')
        if pk:
            self.publication = get_object_or_404(Publication,
                                                 pk=pk)
        else:
            self.publication = None # pragma: no cover

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            # get publication
            publication = serializer.validated_data.get('publication')
            # check permissions on publication
            has_permission = publication.is_editable_by(request.user)
            if not has_permission:
                raise LoggedPermissionDenied(classname=self.__class__.__name__,
                                             resource=request.method)
            return super().post(request, *args, **kwargs)

    class Meta:
        abstract = True


class PublicationRelatedObject(UniCMSCachedRetrieveUpdateDestroyAPIView):
    """
    """
    permission_classes = [IsAdminUser]

    def get_data(self):
        pub_id = self.kwargs['publication_id']
        self.pk = self.kwargs['pk']
        self.publication = get_object_or_404(Publication, pk=pub_id)

    def patch(self, request, *args, **kwargs):
        item = self.get_object()
        # serializer = self.get_serializer(instance=item,
        # data=request.data,
        # partial=True)
        # if serializer.is_valid(raise_exception=True):
        publication = item.publication
        # check permissions on publication
        has_permission = publication.is_editable_by(request.user)
        if not has_permission:
            raise LoggedPermissionDenied(classname=self.__class__.__name__,
                                         resource=request.method)
        return super().patch(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        item = self.get_object()
        publication = item.publication
        # check permissions on publication
        has_permission = publication.is_editable_by(request.user)
        if not has_permission:
            raise LoggedPermissionDenied(classname=self.__class__.__name__,
                                         resource=request.method)
        return super().put(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        item = self.get_object()
        publication = item.publication
        # check permissions on publication
        has_permission = publication.is_editable_by(request.user)
        if not has_permission:
            raise LoggedPermissionDenied(classname=self.__class__.__name__,
                                         resource=request.method)
        return super().delete(request, *args, **kwargs)

    class Meta:
        abstract = True


class PublicationFormView(APIView):

    def get(self, *args, **kwargs):
        form = PublicationForm()
        form_fields = UniCMSFormSerializer.serialize(form)
        return Response(form_fields)


class PublicationEditFormView(APIView):

    def get(self, *args, **kwargs):
        form = PublicationEditForm()
        form_fields = UniCMSFormSerializer.serialize(form)
        return Response(form_fields)


class EditorialBoardPublicationOptionListSchema(AutoSchema):
    def get_operation_id(self, path, method):# pragma: no cover
        return 'listPublicationSelectOptions'


class PublicationOptionList(UniCMSListSelectOptionsAPIView):
    """
    """
    description = ""
    search_fields = ['name', 'title']
    serializer_class = PublicationSelectOptionsSerializer
    queryset = Publication.objects.all()
    schema = EditorialBoardPublicationOptionListSchema()


class PublicationOptionView(generics.RetrieveAPIView):
    """
    """
    description = ""
    permission_classes = [IsAdminUser]
    serializer_class = PublicationSelectOptionsSerializer

    def get_queryset(self):
        """
        """
        pub_id = self.kwargs['pk']
        publications = Publication.objects.filter(pk=pub_id)
        return publications


class PublicationLogsSchema(AutoSchema):
    def get_operation_id(self, path, method):# pragma: no cover
        return 'listPublicationLogs'


class PublicationLogsView(ObjectLogEntriesList):

    schema = PublicationLogsSchema()

    def get_queryset(self, **kwargs):
        """
        """
        object_id = self.kwargs['pk']
        item = Publication.objects.filter(pk=object_id).first()
        content_type_id = ContentType.objects.get_for_model(item).pk
        return super().get_queryset(object_id, content_type_id)


class PublicationRelatedObjectLogsView(ObjectLogEntriesList):

    def get_data(self):
        pub_id = self.kwargs['publication_id']
        self.pk = self.kwargs['pk']
        self.publication = get_object_or_404(Publication, pk=pub_id)

    def get_queryset(self, object_id, content_type_id):
        return super().get_queryset(object_id, content_type_id)
