from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from cms.api.utils import check_user_permission_on_object

from cms.contexts.models import *
from cms.contexts.models_abstract import AbstractLockable

from django.utils.safestring import mark_safe

from cms.medias import settings as cms_media_settings
from cms.medias.models import Media, MediaCollection, AbstractMedia
from cms.medias.validators import *

from cms.pages.models import AbstractPublicable

from cms.templates.models import (TemplateBlock,
                                  ActivableModel,
                                  SectionAbstractModel,
                                  SortableModel,
                                  TimeStampedModel)
from markdown import markdown
from markdownify import markdownify
from taggit.managers import TaggableManager

from . settings import *


CMS_IMAGE_CATEGORY_SIZE = getattr(settings, 'CMS_IMAGE_CATEGORY_SIZE',
                                  cms_media_settings.CMS_IMAGE_CATEGORY_SIZE)


class Category(TimeStampedModel, CreatedModifiedBy):
    name = models.CharField(max_length=160)
    description = models.TextField(max_length=1024)
    image = models.ImageField(upload_to="images/categories",
                              null=True, blank=True,
                              max_length=512,
                              validators=[validate_image_file_extension,
                                          validate_file_size])

    class Meta:
        ordering = ['name']
        verbose_name_plural = _("Content Categories")

    def __str__(self):
        return self.name

    def image_as_html(self):
        res = ""
        try:
            res = f'<img width={CMS_IMAGE_CATEGORY_SIZE} src="{self.image.url}"/>'
        except ValueError:  # pragma: no cover
            # *** ValueError: The 'image' attribute has no file associated with it.
            res = f"{settings.STATIC_URL}images/no-image.jpg"
        return mark_safe(res) # nosec

    image_as_html.short_description = _('Image of this Category')
    image_as_html.allow_tags = True


class AbstractPublication(TimeStampedModel, ActivableModel):
    CONTENT_TYPES = (('markdown', 'markdown'),
                     ('html', 'html'))

    name = models.CharField(max_length=256)
    title = models.CharField(max_length=256, help_text=_('Heading, Headline'))
    subheading = models.TextField(
        max_length=1024, default='', blank=True, help_text=_('Strap line (press)')
    )
    content = models.TextField(default='', blank=True, help_text=_('Content'))
    content_type = models.CharField(choices=CONTENT_TYPES, max_length=33, default='html')
    preview_image = models.ForeignKey(Media, null=True, blank=True,
                                      on_delete=models.PROTECT,
                                      related_name="preview_image")
    presentation_image = models.ForeignKey(Media, null=True, blank=True,
                                           on_delete=models.PROTECT,
                                           related_name="presentation_image")
    # state = models.CharField(choices=PAGE_STATES,
    # max_length=33,
    # default='draft')
    # date_start = models.DateTimeField()
    # date_end = models.DateTimeField()
    category = models.ManyToManyField(Category)

    note = models.TextField(default='', blank=True, help_text=_('Editorial Board notes'))

    class Meta:
        abstract = True
        indexes = [
           models.Index(fields=['title']),
        ]


# class Publication(AbstractPublication, AbstractPublicable, CreatedModifiedBy):
class Publication(AbstractPublication, CreatedModifiedBy, AbstractLockable):
    slug = models.SlugField(default='', blank=True, max_length=256)
    tags = TaggableManager()
    relevance = models.IntegerField(default=0, blank=True)

    class Meta:
        verbose_name_plural = _("Publications")

    def serialize(self):
        return {'slug': self.slug,
                'image': self.image_url(),
                'name': self.name,
                'title': self.title,
                # 'published': self.date_start,
                'subheading': self.subheading,
                'categories': (i.name for i in self.categories),
                'tags': [i.name for i in self.tags.all()],
                'published_in': (f'{i.webpath.site}{i.webpath.fullpath}'
                                 for i in self.publicationcontext_set.all())}

    def active_translations(self):
        return PublicationLocalization.objects.filter(publication=self,
                                                      is_active=True)

    def image_url(self):
        if self.preview_image:
            return self.preview_image.get_media_path()
        elif self.presentation_image:
            return self.presentation_image.get_media_path()
        else: # pragma: no cover
            categories = self.category.all()
            for category in categories:
                if category.image:
                    return sanitize_path(f'{settings.MEDIA_URL}/{category.image}')

    def image_title(self): # pragma: no cover
        if self.preview_image: return self.preview_image.title
        if self.presentation_image: return self.presentation_image.title
        return self.title

    def image_description(self): # pragma: no cover
        if self.preview_image: return self.preview_image.description
        if self.presentation_image: return self.presentation_image.description
        return self.subheading

    @property
    def categories(self):
        return self.category.all()

    @property
    def related_publications(self):
        related = PublicationRelated.objects.filter(publication=self,
                                                    related__is_active=True)
        # return [i for i in related if i.related.is_publicable]
        return [i for i in related]

    @property
    def related_contexts(self, unique_webpath=True, published=True):
        contexts = PublicationContext.objects.select_related('webpath')\
                                             .filter(publication=self,
                                                     is_active=True,
                                                     webpath__is_active=True)
        if published:
            now = timezone.localtime()
            contexts = contexts.filter(date_start__lte=now,
                                       date_end__gte=now)
        if not unique_webpath: return contexts
        webpaths = []
        unique_contexts = []
        for context in contexts:
            if context.webpath in webpaths: continue
            webpaths.append(context.webpath)
            unique_contexts.append(context)
        return unique_contexts

    @property
    def first_available_url(self):
        now = timezone.localtime()
        pubcontx = PublicationContext.objects.filter(publication=self,
                                                     is_active=True,
                                                     webpath__is_active=True,
                                                     date_start__lte=now,
                                                     date_end__gte=now)
        if pubcontx.exists():
            return pubcontx.first().url

    @property
    def related_links(self):
        return self.publicationlink_set.all()

    @property
    def related_embedded_links(self):
        return self.publicationlink_set.all().filter(embedded=True)

    @property
    def related_plain_links(self):
        return self.publicationlink_set.all().filter(embedded=False)

    @property
    def related_media_collections(self):
        if getattr(self, '_related_media_collections', None):
            return self._related_media_collections
        pub_collections = PublicationMediaCollection.objects.filter(publication=self,
                                                                    is_active=True,
                                                                    collection__is_active=True)
        self._related_media_collections = pub_collections
        return self._related_media_collections

    def translate_as(self, lang):
        """
        returns translation if available
        """
        trans = PublicationLocalization.objects.filter(publication=self,
                                                       language=lang,
                                                       is_active=True).first()
        if trans:
            self.title = trans.title
            self.subheading = trans.subheading
            self.content = trans.content

    @property
    def available_in_languages(self) -> list:
        return [(i, i.get_language_display())
                for i in
                PublicationLocalization.objects.filter(publication=self,
                                                       is_active=True)]

    def title2slug(self):
        return slugify(self.title)

    def content_save_switch(self):
        old_content_type = None
        if self.pk:
            current_entry = self.__class__.objects.filter(pk=self.pk).first()
            if current_entry:
                old_content_type = current_entry.content_type

        if all((old_content_type,
                self.content,
                self.pk,
                self.content_type != old_content_type)):

            # markdown to html
            if old_content_type == 'html':
                self.content = markdownify(self.content)
            elif old_content_type == 'markdown':
                self.content = markdown(self.content)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.title2slug()
        self.content_save_switch()
        super(self.__class__, self).save(*args, **kwargs)

    @property
    def get_attachments(self):
        return PublicationAttachment.objects.filter(publication=self,
                                                    is_active=True).\
                                             order_by('order')

    @property
    def get_embedded_attachments(self):
        return self.get_attachments.filter(embedded=True)

    @property
    def get_plain_attachments(self):
        return self.get_attachments.filter(embedded=False)

    def get_publication_contexts(self, webpath=None):
        qdict = dict(publication=self, is_active=True)
        if webpath:
            qdict['webpath'] = webpath
        pub_context = PublicationContext.objects.filter(**qdict)
        return pub_context

    def get_publication_context(self, webpath=None):
        return self.get_publication_contexts(webpath=webpath).first()

    def url(self, webpath=None):
        pub_context = self.get_publication_context(webpath=webpath)
        if not pub_context: return ''
        return pub_context.url

    def get_url_list(self, webpath=None, category_name=None):
        pub_context = self.get_publication_context(webpath=webpath)
        if not pub_context: return ''
        return pub_context.get_url_list(category_name=category_name)

    @property
    def html_content(self):
        content = ''
        if self.content_type == 'markdown':
            content = markdown(self.content)
        elif self.content_type == 'html':
            content = self.content
        return content

    def is_localizable_by(self, user=None):
        if not user: return False

        # check if user has Django permissions to change object
        permission = check_user_permission_on_object(user, self)
        # if permission
        if permission['granted']: return True

        # if no permissions and no locks
        if not permission.get('locked', False):
            # check if user has EditorialBoard translator permissions on object
            pub_ctxs = self.get_publication_contexts()
            for pub_ctx in pub_ctxs:
                webpath = pub_ctx.webpath
                webpath_perms = webpath.is_localizable_by(user=user)
                if webpath_perms: return True
        # if no permissions
        return False

    def is_editable_by(self, user=None):
        if not user: return False

        # check if user has Django permissions to change object
        permission = check_user_permission_on_object(user, self)
        # if permission
        if permission['granted']: return True

        # if no permissions and no locks
        if not permission.get('locked', False):
            # check if user has EditorialBoard editor permissions on object
            pub_ctxs = self.get_publication_contexts()
            for pub_ctx in pub_ctxs:
                webpath = pub_ctx.webpath
                webpath_perms = webpath.is_editable_by(user=user, obj=self)
                if webpath_perms: return True
        # if no permissions
        return False

    @property
    def is_publicable(self) -> bool:
        return self.is_active

    def is_publicable_by(self, user=None):
        if not user: return False

        # check if user has Django permissions to change object
        permission = check_user_permission_on_object(user, self)
        # if permission
        if permission['granted']: return True

        # if no permissions and no locks
        if not permission.get('locked', False):
            # check if user has EditorialBoard editor permissions on object
            pub_ctxs = self.get_publication_contexts()
            for pub_ctx in pub_ctxs:
                webpath = pub_ctx.webpath
                webpath_perms = webpath.is_publicable_by(user=user, obj=self)
                if webpath_perms: return True
        # if no permissions
        return False

    def is_lockable_by(self, user):
        return True if self.is_editable_by(user) else False

    def __str__(self):
        return f'{self.name} ({self.title})'


class AbstractLockablePublicationElement(models.Model):
    class Meta:
        abstract = True

    def is_lockable_by(self, user):
        return True if self.publication.is_editable_by(user) else False


class PublicationContext(TimeStampedModel, ActivableModel,
                         AbstractPublicable, SectionAbstractModel,
                         SortableModel, CreatedModifiedBy):
    publication = models.ForeignKey(Publication, on_delete=models.PROTECT)
    webpath = models.ForeignKey(WebPath, on_delete=models.CASCADE)
    date_start = models.DateTimeField()
    date_end = models.DateTimeField()
    in_evidence_start = models.DateTimeField(null=True,blank=True)
    in_evidence_end = models.DateTimeField(null=True,blank=True)

    class Meta:
        verbose_name_plural = _("Publication Contexts")
        ordering = ['webpath__fullpath', 'order', '-date_start']

    @property
    def path_prefix(self):
        return getattr(settings, 'CMS_PUBLICATION_VIEW_PREFIX_PATH',
                                 CMS_PUBLICATION_VIEW_PREFIX_PATH)

    def get_url_list(self, category_name=None):
        list_prefix = getattr(settings, 'CMS_PUBLICATION_LIST_PREFIX_PATH',
                              CMS_PUBLICATION_LIST_PREFIX_PATH)
        url = sanitize_path(f'{self.webpath.get_full_path()}/{list_prefix}')
        if category_name:
            url += f'/?category_name={category_name.replace(" ", "%20")}'
        return sanitize_path(url)

    # @property
    # def related_publication_contexts(self):
        # related = PublicationContextRelated.objects.filter(publication_context=self,
        # related__is_active=True)
        # return [i for i in related if i.related.is_publicable]

    @property
    def url(self):
        url = f'{self.webpath.get_full_path()}{self.path_prefix}/{self.publication.pk}-{self.publication.slug}/'
        return sanitize_path(url)

    def get_absolute_url(self):
        return self.url

    @property
    def name(self):
        return self.publication.title

    def translate_as(self, *args, **kwargs):
        self.publication.translate_as(*args, **kwargs)

    def serialize(self):
        result = self.publication.serialize()
        result['path'] = self.url
        return result

    @property
    def is_published(self) -> bool:
        now = timezone.localtime()
        return self.date_start <= now and self.date_end > now

    def is_lockable_by(self, user):
        return self.webpath.is_publicable_by(user)

    def __str__(self):
        return '{} {}'.format(self.publication, self.webpath)


class PublicationRelated(TimeStampedModel, SortableModel, ActivableModel,
                         CreatedModifiedBy, AbstractLockablePublicationElement):
    publication = models.ForeignKey(
        Publication, related_name='parent_publication', on_delete=models.CASCADE
    )
    related = models.ForeignKey(
        Publication, on_delete=models.PROTECT, related_name='related_publication'
    )

    class Meta:
        verbose_name_plural = _("Related Publications")
        unique_together = ("publication", "related")

    def __str__(self):
        return '{} {}'.format(self.publication, self.related)


class PublicationLink(TimeStampedModel, CreatedModifiedBy,
                      AbstractLockablePublicationElement):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
    name = models.CharField(max_length=256)
    url = models.URLField(help_text=_("url"))
    embedded = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = _("Publication Links")

    def __str__(self):
        return '{} {}'.format(self.publication, self.name)


class PublicationBlock(SectionAbstractModel,TimeStampedModel,
                       ActivableModel, SortableModel, CreatedModifiedBy,
                       AbstractLockablePublicationElement):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
    block = models.ForeignKey(TemplateBlock, on_delete=models.PROTECT)

    class Meta:
        verbose_name_plural = _("Publication Page Block")

    def __str__(self):
        return '{} {} {}:{}'.format(self.publication,
                                    self.block.name,
                                    self.order or '#',
                                    self.section or '#')


class PublicationMediaCollection(TimeStampedModel, ActivableModel,
                                 SortableModel, CreatedModifiedBy,
                                 AbstractLockablePublicationElement):
    publication = models.ForeignKey(Publication,
                                    on_delete=models.CASCADE)
    collection = models.ForeignKey(MediaCollection,
                                   on_delete=models.PROTECT)

    class Meta:
        verbose_name_plural = _("Publication Media Collection")

    def __str__(self):
        return '{} {}'.format(self.publication, self.collection)


def publication_attachment_path(instance, filename): # pragma: no cover
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'publications_attachments/{}/{}'.format(instance.publication.pk,
                                                   filename)


class PublicationAttachment(TimeStampedModel, SortableModel, ActivableModel,
                            AbstractMedia, CreatedModifiedBy,
                            AbstractLockablePublicationElement):

    publication = models.ForeignKey(
        Publication, related_name='page_attachment', on_delete=models.CASCADE
    )
    name = models.CharField(
        max_length=60,
        blank=True,
        default='',
        help_text=_(
            'Specify the container section in the template where this block would be'
            ' rendered.'
        ),
    )
    file = models.FileField(upload_to=publication_attachment_path,
                            validators=[validate_file_extension,
                                        validate_file_size])
    description = models.TextField()
    embedded = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = _("Publication Attachments")

    def __str__(self):
        return '{} {} ({})'.format(self.publication, self.name,
                                   self.file_type)


class PublicationLocalization(TimeStampedModel, ActivableModel,
                              CreatedModifiedBy, AbstractLockablePublicationElement):
    title = models.CharField(max_length=256, help_text=_('Heading, Headline'))
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
    language = models.CharField(choices=settings.LANGUAGES, max_length=12, default='en')
    subheading = models.TextField(
        max_length=1024, default='', blank=True, help_text=_('Strap line (press)')
    )
    content = models.TextField(default='', blank=True, help_text=_('Content'))

    class Meta:
        verbose_name_plural = _("Publication Localizations")

    def is_lockable_by(self, user):
        return self.publication.is_localizable_by(user)

    def __str__(self):
        return '{} {}'.format(self.publication, self.language)
