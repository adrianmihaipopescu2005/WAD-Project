from flask_wtf import FlaskForm
from wtforms import EmailField, IntegerField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, Regexp

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class AssistantForm(FlaskForm):
    name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    email = EmailField(
        "Email",
        validators=[
            DataRequired(),
            Length(max=255),
            Regexp(EMAIL_PATTERN, message="Enter a valid email address."),
        ],
    )
    password = PasswordField(
        "Temporary password",
        validators=[
            DataRequired(),
            Length(min=8, max=128, message="Password must be at least 8 characters (max 128)."),
        ],
        description="At least 8 characters. Share it with the assistant.",
    )
    submit = SubmitField("Add assistant")


class RemoveAssistantForm(FlaskForm):
    # Rendered by hand per table row (the choices differ per assistant), validated here.
    reassign_to = IntegerField(validators=[Optional()])
