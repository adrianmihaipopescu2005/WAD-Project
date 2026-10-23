from flask_wtf import FlaskForm
from wtforms import EmailField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, Regexp

from ..admin.forms import EMAIL_PATTERN


class StudentForm(FlaskForm):
    student_number = StringField(
        "Student number",
        validators=[
            DataRequired(),
            Length(max=32),
            Regexp(r"^\s*[A-Za-z0-9._/-]+\s*$",
                   message="Use letters, digits and . _ / - only."),
        ],
    )
    first_name = StringField("First name", validators=[DataRequired(), Length(max=80)])
    last_name = StringField("Last name", validators=[DataRequired(), Length(max=80)])
    email = EmailField(
        "Email",
        validators=[
            Optional(),
            Length(max=255),
            Regexp(EMAIL_PATTERN, message="Enter a valid email address."),
        ],
    )
    study_group = StringField("Group", validators=[Optional(), Length(max=32)])
    # Admins only. The route removes this field for assistants.
    assistant_id = SelectField("Lab assistant", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Save")
