from flask_wtf import FlaskForm
from wtforms import EmailField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp

from ..admin.forms import EMAIL_PATTERN


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class AccountLinkForm(FlaskForm):
    name = StringField("Your name", filters=[_strip], validators=[DataRequired(), Length(max=120)])
    email = EmailField(
        "Your email",
        filters=[_strip],
        validators=[
            DataRequired(),
            Length(max=255),
            Regexp(EMAIL_PATTERN, message="Enter a valid email address."),
        ],
        description="The address you use on the absence form. We'll email you a link.",
    )
    submit = SubmitField("Email me a link")


class SetPasswordForm(FlaskForm):
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=8, max=128, message="Password must be at least 8 characters (max 128)."),
        ],
        description="At least 8 characters.",
    )
    confirm = PasswordField(
        "Repeat the password",
        validators=[DataRequired(), EqualTo("password", message="The passwords don't match.")],
    )
    submit = SubmitField("Save password")
