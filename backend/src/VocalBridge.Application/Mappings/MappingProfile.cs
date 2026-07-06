using AutoMapper;
using VocalBridge.Application.DTOs.Translations;
using VocalBridge.Application.DTOs.Videos;
using VocalBridge.Application.DTOs.Audios;
using VocalBridge.Domain.Entities;

namespace VocalBridge.Application.Mappings;

public class MappingProfile : Profile
{
    public MappingProfile()
    {
        // Video → VideoDto
        CreateMap<Video, VideoDto>()
            .ForMember(dest => dest.UploadedAt, opt => opt.MapFrom(src => src.CreatedAt))
            .ForMember(dest => dest.SourceType, opt => opt.MapFrom(src => src.SourceType.ToString()))
            .ForMember(dest => dest.Url, opt => opt.Ignore()); // Populated manually (signed URL or original URL)

        // Audio → AudioDto
        CreateMap<Audio, AudioDto>()
            .ForMember(dest => dest.SourceType, opt => opt.MapFrom(src => src.SourceType.ToString()))
            .ForMember(dest => dest.Url, opt => opt.Ignore()); // Populated manually

        // TranslationJob → TranslationDto
        CreateMap<TranslationJob, TranslationDto>()
            .ForMember(dest => dest.VideoFileName, opt => opt.MapFrom(src => src.Video != null ? src.Video.FileName : string.Empty))
            .ForMember(dest => dest.TranslatedVideoUrl, opt => opt.Ignore()); // Populated manually (signed URL)
    }
}
