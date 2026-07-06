using FluentValidation;
using VocalBridge.Application.DTOs.Translations;

namespace VocalBridge.Application.Validators;

public class CreateTranslationRequestValidator : AbstractValidator<CreateTranslationRequest>
{
    public CreateTranslationRequestValidator()
    {
        // Exactly one source must be provided
        RuleFor(x => x)
            .Must(x => (x.VideoId.HasValue ? 1 : 0) + 
                       (!string.IsNullOrWhiteSpace(x.VideoUrl) ? 1 : 0) + 
                       (x.AudioId.HasValue ? 1 : 0) == 1)
            .WithMessage("Provide exactly one: either VideoId, VideoUrl, or AudioId.");

        // If VideoId is provided, it must be a valid GUID
        RuleFor(x => x.VideoId)
            .NotEqual(Guid.Empty)
            .When(x => x.VideoId.HasValue)
            .WithMessage("VideoId must be a valid GUID.");

        // If VideoUrl is provided, it must be a valid HTTP(S) URL
        RuleFor(x => x.VideoUrl)
            .Must(url => Uri.TryCreate(url, UriKind.Absolute, out var uri) &&
                         (uri.Scheme == Uri.UriSchemeHttp || uri.Scheme == Uri.UriSchemeHttps))
            .When(x => !string.IsNullOrWhiteSpace(x.VideoUrl))
            .WithMessage("VideoUrl must be a valid HTTP or HTTPS URL.");

        // If AudioId is provided, it must be a valid GUID
        RuleFor(x => x.AudioId)
            .NotEqual(Guid.Empty)
            .When(x => x.AudioId.HasValue)
            .WithMessage("AudioId must be a valid GUID.");
    }
}
