from flask_wtf import FlaskForm
from wtforms import BooleanField, EmailField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length


class LoginForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(max=128)])
    remember = BooleanField("Remember me")
    submit = SubmitField("Log in")


class LogoutForm(FlaskForm):
    """Empty form, used only for its CSRF token on the logout POST."""
