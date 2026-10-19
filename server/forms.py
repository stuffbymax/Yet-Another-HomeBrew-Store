import re

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import BooleanField, PasswordField, SelectField, StringField, TextAreaField
from wtforms.validators import (DataRequired, Email, EqualTo, Length, Optional,
                                Regexp, ValidationError)

_CTRL = re.compile(r"[\x00-\x1f\x7f]")


def no_control_chars(form, field):
    if field.data and _CTRL.search(field.data):
        raise ValidationError("Control characters are not allowed.")


class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[
        DataRequired(), Regexp(r"^[A-Za-z0-9_]{3,32}$",
                               message="3-32 letters, numbers or underscores.")])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[
        DataRequired(), Length(min=12, max=128, message="Use 12-128 characters.")])
    confirm = PasswordField("Repeat password", validators=[
        DataRequired(), EqualTo("password", message="Passwords do not match.")])
    accept = BooleanField("I accept the rules", validators=[DataRequired()])


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(max=32)])
    password = PasswordField("Password", validators=[DataRequired(), Length(max=128)])


class AppForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(2, 64), no_control_chars])
    platform = SelectField("Platform", choices=[("ps3", "PS3"), ("ps4", "PS4"), ("ps5", "PS5")])
    version = StringField("Version", validators=[
        DataRequired(), Regexp(r"^[0-9A-Za-z.+_-]{1,20}$", message="Letters, digits . + _ - only.")])
    title_id = StringField("Title ID (optional)", validators=[
        Optional(), Regexp(r"^[A-Za-z0-9_-]{1,24}$", message="Letters, digits, _ and - only.")])
    short_desc = StringField("One-line summary", validators=[Length(max=140), no_control_chars])
    description = TextAreaField("Description", validators=[Length(max=4000)])
    icon = FileField("Icon (PNG or JPG, optional)")
    package = FileField("Package (.pkg, .zip or .elf)")
    accept = BooleanField("This is my own work, or I have the right to distribute it. "
                          "It contains no pirated or commercial game content.")


class ConfirmForm(FlaskForm):
    """CSRF-only form for POST buttons (delete, approve, reject)."""


class ForgotForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])


class ResetForm(FlaskForm):
    password = PasswordField("New password", validators=[DataRequired(), Length(min=12, max=128)])
    confirm = PasswordField("Repeat password", validators=[DataRequired(), EqualTo("password", message="Passwords do not match.")])


class TotpForm(FlaskForm):
    code = StringField("6-digit code", validators=[DataRequired(), Regexp(r"^\d{6}$", message="Enter the 6 digits.")])


class PasswordForm(FlaskForm):
    password = PasswordField("Current password", validators=[DataRequired(), Length(max=128)])


class ReportForm(FlaskForm):
    reason = TextAreaField("What is wrong with this app?", validators=[DataRequired(), Length(10, 500)])
