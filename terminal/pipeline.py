from terminal.models import UserProfile, TokenWallet


def save_profile(backend, user, response, *args, **kwargs):
    """
    Called after Google OAuth creates a new user.
    Sets up their Orion profile automatically.
    """
    if backend.name == 'google-oauth2':
        # Save email from Google if not already set
        if not user.email and response.get('email'):
            user.email = response.get('email')
            user.save()

        # Create profile if it doesn't exist
        profile, created = UserProfile.objects.get_or_create(user=user)

        # Create token wallet if it doesn't exist
        wallet, _ = TokenWallet.objects.get_or_create(user=user)
        if created:
            # New user gets 10 tokens
            wallet.tokens = 10
            wallet.total_earned = 10
            wallet.save()
