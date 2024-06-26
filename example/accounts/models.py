from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import AbstractUser
from django.contrib.auth import get_user_model
from django.conf import settings


class User(AbstractUser):
    first_name = models.CharField(_('Name'), max_length=250,  # django-doctor: disable=nullable-string-field
                                  blank=True, null=True)
    last_name = models.CharField(_('Surname'), max_length=250,  # django-doctor: disable=nullable-string-field
                                 blank=True, null=True)
    is_active = models.BooleanField(_('active'), default=True)
    email = models.EmailField(_('email address'), blank=True, null=True)  # django-doctor: disable=nullable-string-field
    taxpayer_id = models.CharField(_("Taxpayer's identification number"),  # django-doctor: disable=nullable-string-field
                                   max_length=32,
                                   blank=True, null=True)
    matricola_studente = models.CharField(max_length=255,  # django-doctor: disable=nullable-string-field
                                          blank=True, null=True)
    matricola_dipendente = models.CharField(max_length=255,  # django-doctor: disable=nullable-string-field
                                            blank=True, null=True)

    def __str__(self):
        return f'{self.first_name} {self.last_name}'
    
    class Meta:
        ordering = ['username']
        verbose_name_plural = _("Users")
