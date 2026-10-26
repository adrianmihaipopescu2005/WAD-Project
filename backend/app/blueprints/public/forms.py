from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length

from ..absences.forms import AbsenceFieldsForm


class PublicAbsenceForm(AbsenceFieldsForm):
    student_number = StringField(
        "Student number",
        validators=[DataRequired(), Length(max=32)],
        description="The number your lab assistant registered you with.",
    )
    submit = SubmitField("Report absence")
