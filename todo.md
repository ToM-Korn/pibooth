# Todo
## Porser Config 
- add PICTURE -> footer_logo functions
- add WINDOW -> orientation functions 
- add CAMERA -> imageformat link to camera/base.py
- add PRINTER -> format -> stripe functions 
- add PICTURE -> pic_postfix 

## Portrait mode Layout 
for screen in portrait mode 

 -> started with 

` parser setting WINDOW orientation  which is passed through 
booth.py -> window.py -> background.py and sets the config there 
`


## Add Templating system
that sets up the composition from the event/template folder 

### Templates for Strips 
for strips in cp70

## Printer 
autochoose available printer 
no need to set it in main settings 

## Logging 
log to event folder
 -> done in booth.py
 ->        filename = osp.join(options.config_directory, 'pibooth.log') # tk edit -> log to event folder


# Credits 
go image -> Bild von <a href="https://pixabay.com/de/users/peggy_marco-1553824/?utm_source=link-attribution&utm_medium=referral&utm_campaign=image&utm_content=1015629">Peggy und Marco Lachmann-Anke</a> auf <a href="https://pixabay.com/de//?utm_source=link-attribution&utm_medium=referral&utm_campaign=image&utm_content=1015629">Pixabay</a>
