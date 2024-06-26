from cms.api.serializers import (UniCMSContentTypeClass,
                                 UniCMSCreateUpdateSerializer,
                                 UniCMSTagsValidator)
from cms.contexts.models import WebPath
from cms.contexts.serializers import WebPathSerializer
from cms.medias.serializers import MediaSerializer, MediaCollectionSerializer
from cms.templates.utils import secure_url

from rest_framework import serializers

from taggit_serializer.serializers import (TagListSerializerField,
                                           TaggitSerializer)

from . models import *


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


class PublicationForeignKey(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        request = self.context.get('request', None)
        if request:
            publication_id = self.context['request'].parser_context['kwargs']['publication_id']
            return Publication.objects.filter(pk=publication_id)
        return None # pragma: no cover


class WebPathForeignKey(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        request = self.context.get('request', None)
        if request:
            if request.method in ['PATCH','PUT']:
                return WebPath.objects.all()
            site_id = self.context['request'].parser_context['kwargs']['site_id']
            webpath_id = self.context['request'].parser_context['kwargs']['webpath_id']
            return WebPath.objects.filter(pk=webpath_id,
                                          site__id=site_id)
        return None # pragma: no cover


class PublicationSerializer(TaggitSerializer,
                            UniCMSCreateUpdateSerializer,
                            UniCMSContentTypeClass,
                            UniCMSTagsValidator):
    tags = TagListSerializerField()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.preview_image:
            preview_image = MediaSerializer(instance.preview_image)
            data['preview_image'] = preview_image.data
        if instance.presentation_image:
            presentation_image = MediaSerializer(instance.presentation_image)
            data['presentation_image'] = presentation_image.data
        data['image'] = instance.image_url()
        categories = []
        for category in instance.category.all():
            categories.append(CategorySerializer(category).data)
        data['category_data'] = categories
        data['full_name'] = instance.__str__()
        return data

    class Meta:
        model = Publication
        fields = '__all__'
        read_only_fields = ('created_by', 'modified_by', 'content_type')


class PublicationSelectOptionsSerializer(serializers.ModelSerializer):

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['value'] = instance.pk
        data['text'] = instance.__str__()
        return data

    class Meta:
        model = Publication
        fields = ()


class PublicationContextSerializer(UniCMSCreateUpdateSerializer,
                                   UniCMSContentTypeClass):
    webpath = WebPathForeignKey()

    def to_internal_value(self, data):
        if data.get('in_evidence_start') == '':
            data['in_evidence_start'] = None
        if data.get('in_evidence_end') == '':
            data['in_evidence_end'] = None
        return super().to_internal_value(data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.publication:
            publication = PublicationSerializer(instance.publication)
            data['publication'] = publication.data
        if instance.webpath:
            webpath = WebPathSerializer(instance.webpath)
            data['webpath'] = webpath.data
        data['path'] = instance.url
        return data

    class Meta:
        model = PublicationContext
        fields = '__all__'
        read_only_fields = ('created_by', 'modified_by')


class PublicationContextSelectOptionsSerializer(serializers.ModelSerializer):

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['value'] = instance.pk
        data['text'] = instance.__str__()
        return data

    class Meta:
        model = PublicationContext
        fields = ()


class PublicationAttachmentSerializer(UniCMSCreateUpdateSerializer,
                                      UniCMSContentTypeClass):
    publication = PublicationForeignKey()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['file'] = secure_url(data['file'])
        return data

    class Meta:
        model = PublicationAttachment
        fields = '__all__'
        read_only_fields = ('created_by', 'modified_by', 'file_size','file_type')


class PublicationBlockSerializer(UniCMSCreateUpdateSerializer,
                                 UniCMSContentTypeClass):
    publication = PublicationForeignKey()

    class Meta:
        model = PublicationBlock
        fields = '__all__'


class PublicationMediaCollectionSerializer(UniCMSCreateUpdateSerializer,
                                           UniCMSContentTypeClass):
    publication = PublicationForeignKey()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.collection:
            collection = MediaCollectionSerializer(instance.collection)
            data['collection'] = collection.data
        return data

    class Meta:
        model = PublicationMediaCollection
        fields = '__all__'


class PublicationLinkSerializer(UniCMSCreateUpdateSerializer,
                                UniCMSContentTypeClass):
    publication = PublicationForeignKey()

    class Meta:
        model = PublicationLink
        fields = '__all__'


class PublicationLocalizationSerializer(UniCMSCreateUpdateSerializer,
                                        UniCMSContentTypeClass):
    publication = PublicationForeignKey()

    class Meta:
        model = PublicationLocalization
        fields = '__all__'


class PublicationRelatedSerializer(UniCMSCreateUpdateSerializer,
                                   UniCMSContentTypeClass):
    publication = PublicationForeignKey()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.related:
            related = PublicationSerializer(instance.related)
            data['related'] = related.data
        return data

    class Meta:
        model = PublicationRelated
        fields = '__all__'
